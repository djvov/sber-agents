"""
Инструменты для ReAct агента

Инструменты - это функции, которые агент может вызывать для получения информации.
Декоратор @tool из LangChain автоматически создает описание для LLM.
"""
import json
import logging
from langchain_core.tools import tool
import rag

logger = logging.getLogger(__name__)

@tool
def rag_search(query: str) -> str:
    """
    Ищет информацию в документах Сбербанка (условия кредитов, вкладов и других банковских продуктов).
    
    Возвращает JSON со списком источников, где каждый источник содержит:
    - source: имя файла
    - page: номер страницы (только для PDF)
    - page_content: текст документа
    """
    try:
        # Получаем релевантные документы через RAG (retrieval + reranking)
        documents = rag.retrieve_documents(query)
        
        if not documents:
            return json.dumps({"sources": []}, ensure_ascii=False)
        
        # Формируем структурированный ответ для агента
        sources = []
        for doc in documents:
            source_data = {
                "source": doc.metadata.get("source", "Unknown"),
                "page_content": doc.page_content  # Полный текст документа
            }
            # page только для PDF (у JSON документов его нет)
            if "page" in doc.metadata:
                source_data["page"] = doc.metadata["page"]
            sources.append(source_data)
        
        # ensure_ascii=False для корректной кириллицы
        return json.dumps({"sources": sources}, ensure_ascii=False)
        
    except Exception as e:
        logger.error(f"Error in rag_search: {e}", exc_info=True)
        return json.dumps({"sources": []}, ensure_ascii=False)


@tool
def currency_converter(amount: float, from_currency: str, to_currency: str) -> str:
    """
    Конвертирует сумму из одной валюты в другую, используя актуальные курсы от API.
    
    Args:
        amount: Сумма для конвертации
        from_currency: Исходная валюта (например, USD, EUR, RUB)
        to_currency: Целевая валюта (например, USD, EUR, RUB)
    
    Returns:
        Строка с результатом конвертации
    """
    import requests
    import json
    from config import config
    
    try:
        # Формируем URL для запроса к API
        api_url = f"{config.EXCHANGERATE_URL}{from_currency.upper()}"
        
        # Выполняем запрос к API
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()  # Проверяем HTTP ошибки
        
        # Парсим JSON ответ
        data = response.json()
        
        # Проверяем успешность запроса
        if data.get("result") != "success":
            return f"Ошибка API: не удалось получить курсы валют для {from_currency.upper()}"
        
        # Получаем курсы валют
        conversion_rates = data.get("conversion_rates", {})
        
        # Проверяем наличие целевой валюты
        if to_currency.upper() not in conversion_rates:
            return f"Ошибка: валюта '{to_currency}' не найдена в курсах {from_currency.upper()}"
        
        # Получаем курс и вычисляем результат
        rate = conversion_rates[to_currency.upper()]
        converted_amount = amount * rate
        
        return f"{amount} {from_currency.upper()} = {converted_amount:.2f} {to_currency.upper()}"
    
    except requests.exceptions.Timeout:
        return "Ошибка: превышено время ожидания ответа от API курсов валют"
    except requests.exceptions.RequestException as e:
        return f"Ошибка сети при получении курсов валют: {str(e)}"
    except json.JSONDecodeError:
        return "Ошибка: не удалось распарсить ответ API"
    except Exception as e:
        return f"Ошибка при конвертации валют: {str(e)}"

