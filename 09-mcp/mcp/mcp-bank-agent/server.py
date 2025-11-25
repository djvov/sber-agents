#!/usr/bin/env python3
"""
Bank Agent MCP Server

Предоставляет два инструмента для банковского агента:
1. search_products - поиск актуальных продуктов банка (вклады, кредиты, карты)
2. currency_converter - конвертация валют по курсам ЦБ РФ

Транспорт: streamable-http (HTTP MCP server)
Порт: 8000 (по умолчанию для FastMCP)
"""
import json
import logging
import os
from pathlib import Path
from typing import Annotated, Literal
import requests
from pydantic import Field

from mcp.server.fastmcp import FastMCP

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-bank-agent")

# Path to the products database
PRODUCTS_DB_PATH = Path(__file__).parent / "data" / "bank_products.json"

# CBR API endpoint
CBR_API_URL = "https://www.cbr-xml-daily.ru/latest.js"


def load_products() -> list[dict]:
    """Загрузка продуктов банка из JSON файла."""
    try:
        if not PRODUCTS_DB_PATH.exists():
            logger.error(f"Products database not found at {PRODUCTS_DB_PATH}")
            return []
        
        with open(PRODUCTS_DB_PATH, 'r', encoding='utf-8') as f:
            products = json.load(f)
        
        logger.info(f"Loaded {len(products)} products from database")
        return products
    except Exception as e:
        logger.error(f"Error loading products: {e}")
        return []


def filter_products(
    products: list[dict],
    product_type: str | None = None,
    keyword: str | None = None,
    min_amount: int | None = None,
    max_amount: int | None = None,
    min_rate: float | None = None,
    max_rate: float | None = None,
    currency: str | None = None
) -> list[dict]:
    """
    Фильтрация продуктов по параметрам
    
    Использует list comprehension для простоты (следуя принципу KISS).
    """
    filtered = products
    
    # Фильтр по типу продукта
    if product_type:
        filtered = [p for p in filtered if p.get('product_type') == product_type]
    
    # Поиск по ключевому слову (в названии и описании)
    if keyword:
        keyword_lower = keyword.lower()
        filtered = [
            p for p in filtered
            if keyword_lower in p.get('name', '').lower() or 
               keyword_lower in p.get('description', '').lower()
        ]
    
    # Фильтр по минимальной сумме
    if min_amount is not None:
        filtered = [p for p in filtered if p.get('amount_min', 0) <= min_amount]
    
    # Фильтр по максимальной сумме
    if max_amount is not None:
        filtered = [p for p in filtered if p.get('amount_max', float('inf')) >= max_amount]
    
    # Фильтр по минимальной ставке
    if min_rate is not None:
        filtered = [p for p in filtered if p.get('rate_max', 0) >= min_rate]
    
    # Фильтр по максимальной ставке
    if max_rate is not None:
        filtered = [p for p in filtered if p.get('rate_min', float('inf')) <= max_rate]
    
    # Фильтр по валюте
    if currency:
        filtered = [p for p in filtered if currency in p.get('currency', '')]
    
    return filtered


def format_products(products: list[dict], limit: int = 10) -> str:
    """
    Форматирование списка продуктов для агента
    
    Возвращает топ-N продуктов с основной информацией.
    """
    if not products:
        return "Продукты не найдены по заданным критериям."
    
    # Ограничиваем количество результатов
    products = products[:limit]
    
    result = f"Найдено {len(products)} продукт(ов):\n\n"
    
    for i, product in enumerate(products, 1):
        result += f"**{i}. {product.get('name')}**\n"
        result += f"   Описание: {product.get('description')}\n"
        
        # Ставка (для вкладов и кредитов)
        rate_min = product.get('rate_min', 0)
        rate_max = product.get('rate_max', 0)
        if rate_min > 0 or rate_max > 0:
            if rate_min == rate_max:
                result += f"   Ставка: {rate_min}% годовых\n"
            else:
                result += f"   Ставка: от {rate_min}% до {rate_max}% годовых\n"
        
        # Сумма
        amount_min = product.get('amount_min', 0)
        amount_max = product.get('amount_max', 0)
        if amount_min > 0 or amount_max > 0:
            if amount_max > 0:
                result += f"   Сумма: от {amount_min:,} до {amount_max:,} {product.get('currency', 'RUB')}\n"
            else:
                result += f"   Сумма: от {amount_min:,} {product.get('currency', 'RUB')}\n"
        
        # Срок
        term = product.get('term_months', '')
        if term:
            result += f"   Срок: {term} месяцев\n"
        
        # Особенности
        features = product.get('features', [])
        if features:
            result += f"   Особенности: {', '.join(features)}\n"
        
        result += "\n"
    
    return result


def get_exchange_rates() -> dict:
    """
    Получение курсов валют от ЦБ РФ
    
    API возвращает курсы относительно рубля (base: RUB).
    Например: {"USD": 0.0124} означает 1 RUB = 0.0124 USD (или 1 USD ≈ 80.6 RUB)
    """
    try:
        response = requests.get(CBR_API_URL, timeout=5)
        response.raise_for_status()
        data = response.json()
        return data.get('rates', {})
    except requests.RequestException as e:
        logger.error(f"Error fetching exchange rates: {e}")
        return {}


def convert_currency(
    from_currency: str,
    to_currency: str,
    amount: float | None,
    rates: dict
) -> tuple[float | None, str]:
    """
    Конвертация валюты через рубль
    
    Логика:
    - RUB → другая валюта: amount * rates[to_currency]
    - другая валюта → RUB: amount / rates[from_currency]
    - валюта1 → валюта2: amount / rates[from] * rates[to] (через рубли)
    
    Returns:
        (converted_amount, formatted_string)
    """
    if not rates:
        return None, "Не удалось получить курсы валют от ЦБ РФ"
    
    # Проверка поддержки валют
    if from_currency != "RUB" and from_currency not in rates:
        return None, f"Валюта {from_currency} не поддерживается"
    
    if to_currency != "RUB" and to_currency not in rates:
        return None, f"Валюта {to_currency} не поддерживается"
    
    # Одинаковые валюты
    if from_currency == to_currency:
        rate_str = f"1 {from_currency} = 1 {to_currency}"
        if amount:
            return amount, f"{amount:,.2f} {from_currency} = {amount:,.2f} {to_currency}"
        return 1.0, rate_str
    
    # Конвертация через рубль
    if from_currency == "RUB":
        # RUB → другая валюта
        rate = rates[to_currency]
        rate_str = f"1 RUB = {rate:.6f} {to_currency} (или 1 {to_currency} ≈ {1/rate:.2f} RUB)"
        if amount:
            converted = amount * rate
            return converted, f"{amount:,.2f} RUB = {converted:,.2f} {to_currency}\n\nТекущий курс: {rate_str}"
        return rate, rate_str
    
    elif to_currency == "RUB":
        # другая валюта → RUB
        rate = rates[from_currency]
        rate_str = f"1 {from_currency} = {1/rate:.2f} RUB (или 1 RUB = {rate:.6f} {from_currency})"
        if amount:
            converted = amount / rate
            return converted, f"{amount:,.2f} {from_currency} = {converted:,.2f} RUB\n\nТекущий курс: {rate_str}"
        return 1/rate, rate_str
    
    else:
        # валюта1 → валюта2 (через рубль)
        rate_from = rates[from_currency]  # from → RUB
        rate_to = rates[to_currency]      # RUB → to
        rate = (1 / rate_from) * rate_to  # итоговый курс from → to
        
        rate_str = f"1 {from_currency} = {rate:.4f} {to_currency}"
        if amount:
            converted = amount * rate
            return converted, f"{amount:,.2f} {from_currency} = {converted:,.2f} {to_currency}\n\nТекущий курс: {rate_str}"
        return rate, rate_str


def calculate_deposit_profitability(
    initial_amount: float,
    annual_rate: float,
    term_months: int,
    compounding_frequency: str
) -> tuple[float, float, float]:
    """
    Расчет доходности вклада с учетом капитализации процентов
    
    Формула сложного процента: A = P * (1 + r/n)^(n*t)
    
    Args:
        initial_amount: Начальная сумма вклада
        annual_rate: Годовая процентная ставка (в процентах)
        term_months: Срок вклада в месяцах
        compounding_frequency: Частота капитализации ('monthly', 'quarterly', 'annually')
    
    Returns:
        (final_amount, interest_earned, effective_rate)
    """
    # Проверка входных данных
    if initial_amount <= 0:
        raise ValueError("Начальная сумма должна быть положительной")
    if annual_rate < 0:
        raise ValueError("Процентная ставка не может быть отрицательной")
    if term_months <= 0:
        raise ValueError("Срок вклада должен быть положительным")
    
    # Определение количества периодов капитализации в году
    frequency_map = {
        'monthly': 12,
        'quarterly': 4,
        'annually': 1
    }
    
    if compounding_frequency not in frequency_map:
        raise ValueError(f"Неподдерживаемая частота капитализации: {compounding_frequency}")
    
    n = frequency_map[compounding_frequency]  # количество периодов в году
    t = term_months / 12  # срок в годах
    r = annual_rate / 100  # ставка в десятичном виде
    
    # Расчет итоговой суммы
    final_amount = initial_amount * (1 + r/n)**(n*t)
    
    # Расчет дохода
    interest_earned = final_amount - initial_amount
    
    # Расчет эффективной ставки
    effective_rate = ((final_amount / initial_amount) - 1) * 100
    
    return final_amount, interest_earned, effective_rate


# Create FastMCP server
mcp = FastMCP("mcp-bank-agent", dependencies=["requests>=2.31.0"])


@mcp.tool(
    name="search_products",
    description="Универсальный поиск актуальных продуктов банка (вклады, кредиты, карты, счета) с гибкой фильтрацией",
)
async def search_products(
    product_type: Annotated[
        Literal["deposit", "credit", "debit_card", "credit_card", "account"] | None,
        Field(
            description="Тип продукта для фильтрации",
        )
    ] = None,
    keyword: Annotated[
        str | None,
        Field(
            description="Ключевое слово для поиска в названии и описании продукта",
            min_length=2,
            max_length=100,
            examples=["вклад", "кредит", "карта", "кешбэк"]
        )
    ] = None,
    min_amount: Annotated[
        int | None,
        Field(
            description="Минимальная сумма (ищет продукты доступные от этой суммы)",
            ge=0,
            examples=[10000, 50000, 100000]
        )
    ] = None,
    max_amount: Annotated[
        int | None,
        Field(
            description="Максимальная сумма (ищет продукты доступные до этой суммы)",
            ge=0,
            examples=[1000000, 5000000]
        )
    ] = None,
    min_rate: Annotated[
        float | None,
        Field(
            description="Минимальная процентная ставка (для вкладов и кредитов)",
            ge=0,
            le=100,
            examples=[10.0, 15.0, 20.0]
        )
    ] = None,
    max_rate: Annotated[
        float | None,
        Field(
            description="Максимальная процентная ставка (для вкладов и кредитов)",
            ge=0,
            le=100,
            examples=[15.0, 20.0, 25.0]
        )
    ] = None,
    currency: Annotated[
        Literal["RUB", "USD", "EUR"] | None,
        Field(
            description="Валюта продукта"
        )
    ] = None
) -> str:
    """
    Поиск актуальных банковских продуктов с фильтрацией
    
    Этот инструмент ищет текущие продукты банка с актуальными ставками и условиями.
    В отличие от rag_search (статические PDF), здесь динамические данные о продуктах.
    
    Args:
        product_type: Тип продукта (вклад, кредит, карта, счёт)
        keyword: Поиск по ключевому слову
        min_amount: Минимальная сумма
        max_amount: Максимальная сумма
        min_rate: Минимальная ставка
        max_rate: Максимальная ставка
        currency: Валюта
    
    Returns:
        Форматированный список найденных продуктов (топ-10)
    """
    logger.info(f"search_products called with: type={product_type}, keyword={keyword}, "
                f"amount={min_amount}-{max_amount}, rate={min_rate}-{max_rate}, currency={currency}")
    
    # Загружаем продукты
    products = load_products()
    if not products:
        return "Не удалось загрузить базу продуктов банка"
    
    # Фильтруем
    filtered = filter_products(
        products,
        product_type=product_type,
        keyword=keyword,
        min_amount=min_amount,
        max_amount=max_amount,
        min_rate=min_rate,
        max_rate=max_rate,
        currency=currency
    )
    
    # Форматируем результат
    return format_products(filtered)


@mcp.tool(
    name="currency_converter",
    description="Конвертация валют по актуальным курсам ЦБ РФ с поддержкой всех основных валют",
)
async def currency_converter(
    from_currency: Annotated[
        Literal["RUB", "USD", "EUR", "CNY", "GBP", "CHF", "JPY", "TRY"],
        Field(
            description="Исходная валюта для конвертации"
        )
    ] = "USD",
    to_currency: Annotated[
        Literal["RUB", "USD", "EUR", "CNY", "GBP", "CHF", "JPY", "TRY"],
        Field(
            description="Целевая валюта для конвертации"
        )
    ] = "RUB",
    amount: Annotated[
        float | None,
        Field(
            description="Сумма для конвертации (если не указана, вернется только курс)",
            ge=0,
            examples=[100, 1000, 10000]
        )
    ] = None
) -> str:
    """
    Конвертация валют по актуальным курсам ЦБ РФ
    
    Поддерживает конвертацию между любыми валютами (не только с рублями).
    Данные обновляются ежедневно ЦБ РФ.
    
    Args:
        from_currency: Исходная валюта
        to_currency: Целевая валюта
        amount: Сумма для конвертации (опционально)
    
    Returns:
        Результат конвертации с текущим курсом
    """
    logger.info(f"currency_converter called: {amount} {from_currency} -> {to_currency}")
    
    # Получаем актуальные курсы
    rates = get_exchange_rates()
    
    # Конвертируем
    converted_amount, result_str = convert_currency(from_currency, to_currency, amount, rates)
    
    if converted_amount is None:
        return result_str  # Сообщение об ошибке
    
    return result_str


@mcp.tool(
    name="calculate_deposit_profitability",
    description="Расчет доходности вклада с учетом капитализации процентов (ежемесячно, ежеквартально, ежегодно)",
)
async def calculate_deposit_profitability_tool(
    initial_amount: Annotated[
        float,
        Field(
            description="Начальная сумма вклада",
            ge=0.01,
            examples=[100000, 500000, 1000000]
        )
    ],
    annual_rate: Annotated[
        float,
        Field(
            description="Годовая процентная ставка (в процентах)",
            ge=0,
            le=100,
            examples=[10.0, 15.0, 20.0]
        )
    ],
    term_months: Annotated[
        int,
        Field(
            description="Срок вклада в месяцах",
            ge=1,
            le=1200,  # максимум 100 лет
            examples=[3, 6, 12, 24, 36]
        )
    ],
    compounding_frequency: Annotated[
        Literal["monthly", "quarterly", "annually"],
        Field(
            description="Частота капитализации процентов",
            examples=["monthly", "quarterly", "annually"]
        )
    ]
) -> str:
    """
    Расчет доходности вклада с учетом сложных процентов
    
    Этот инструмент рассчитывает итоговую сумму вклада и полученный доход
    с учетом выбранной частоты капитализации процентов.
    
    Args:
        initial_amount: Начальная сумма вклада
        annual_rate: Годовая процентная ставка в процентах
        term_months: Срок вклада в месяцах
        compounding_frequency: Частота капитализации (monthly=ежемесячно, quarterly=ежеквартально, annually=ежегодно)
    
    Returns:
        Детальный расчет с итоговой суммой, доходом и эффективной ставкой
    """
    logger.info(f"calculate_deposit_profitability called: {initial_amount} RUB, "
                f"{annual_rate}% годовых, {term_months} мес., {compounding_frequency}")
    
    try:
        final_amount, interest_earned, effective_rate = calculate_deposit_profitability(
            initial_amount=initial_amount,
            annual_rate=annual_rate,
            term_months=term_months,
            compounding_frequency=compounding_frequency
        )
        
        # Форматирование результата
        result = f"**Расчет доходности вклада**\n\n"
        result += f"📊 **Исходные данные:**\n"
        result += f"• Начальная сумма: {initial_amount:,.2f} ₽\n"
        result += f"• Процентная ставка: {annual_rate}% годовых\n"
        result += f"• Срок: {term_months} месяцев ({term_months/12:.1f} года)\n"
        
        # Перевод частоты на русский
        frequency_names = {
            'monthly': 'ежемесячно',
            'quarterly': 'ежеквартально', 
            'annually': 'ежегодно'
        }
        result += f"• Капитализация: {frequency_names[compounding_frequency]}\n\n"
        
        result += f"💰 **Результат расчета:**\n"
        result += f"• Итоговая сумма: {final_amount:,.2f} ₽\n"
        result += f"• Доход: {interest_earned:,.2f} ₽\n"
        result += f"• Эффективная ставка: {effective_rate:.2f}%\n\n"
        
        # Дополнительная информация
        if compounding_frequency == 'monthly':
            result += f"📈 При ежемесячной капитализации проценты начисляются 12 раз в год\n"
        elif compounding_frequency == 'quarterly':
            result += f"📈 При ежеквартальной капитализации проценты начисляются 4 раза в год\n"
        else:
            result += f"📈 При ежегодной капитализации проценты начисляются 1 раз в год\n"
        
        result += f"\n💡 **Примечание:** Расчет выполнен по формуле сложных процентов с учетом выбранной частоты капитализации."
        
        return result
        
    except ValueError as e:
        logger.error(f"Calculation error: {e}")
        return f"❌ Ошибка в расчете: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return f"❌ Неожиданная ошибка при расчете: {str(e)}"


if __name__ == "__main__":
    logger.info("Starting Bank Agent MCP Server...")
    logger.info(f"Products database: {PRODUCTS_DB_PATH}")
    logger.info(f"Currency API: {CBR_API_URL}")
    
    # Проверяем наличие базы продуктов
    if not PRODUCTS_DB_PATH.exists():
        logger.error(f"Products database not found at {PRODUCTS_DB_PATH}")
        logger.error("Please create data/bank_products.json before starting the server")
        exit(1)
    
    # Получаем порт из переменной окружения (по умолчанию 8000)
    port = int(os.getenv("PORT", "8000"))
    logger.info(f"Server will be available at: http://localhost:{port}/mcp")
    
    # Запускаем сервер
    mcp.run(transport="streamable-http")

