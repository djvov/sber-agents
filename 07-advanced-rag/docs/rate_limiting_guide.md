# Руководство по Rate Limiting

## Проблема

При выполнении команды `/evaluate_dataset` могут возникать ошибки связанные с слишком частыми запросами к API:

- `Rate limit exceeded` - превышен лимит запросов
- `Too many requests` - слишком много запросов
- `429 Too Many Requests` - HTTP ошибка от API провайдера

## Решение

В проекте реализована система настраиваемых задержек между API запросами во время evaluation через прямые вызовы `time.sleep()`.

## Настройка задержек

### В файле `.env` добавьте параметры:

```bash
# Задержка между RAG запросами (секунды)
# Рекомендуется: 1.0-3.0 для OpenAI, 0.5-1.0 для локальных моделей
EVALUATION_RAG_DELAY=1.0

# Задержка между RAGAS метриками (секунды)  
# Рекомендуется: 0.5-1.0
EVALUATION_METRIC_DELAY=0.5

# Задержка между embeddings запросами (секунды)
# Рекомендуется: 0.2-0.5
EVALUATION_EMBEDDING_DELAY=0.2

# Задержка между LangSmith API вызовами (секунды)
# Рекомендуется: 0.1-0.3
EVALUATION_LANGSMITH_DELAY=0.1
```

## Рекомендации по настройке

### Для разных API провайдеров:

#### OpenAI API
```bash
EVALUATION_RAG_DELAY=2.0
EVALUATION_METRIC_DELAY=1.0
EVALUATION_EMBEDDING_DELAY=0.5
EVALUATION_LANGSMITH_DELAY=0.2
```

#### OpenRouter
```bash
EVALUATION_RAG_DELAY=1.5
EVALUATION_METRIC_DELAY=0.8
EVALUATION_EMBEDDING_DELAY=0.3
EVALUATION_LANGSMITH_DELAY=0.1
```

#### Fireworks
```bash
EVALUATION_RAG_DELAY=1.0
EVALUATION_METRIC_DELAY=0.5
EVALUATION_EMBEDDING_DELAY=0.2
EVALUATION_LANGSMITH_DELAY=0.1
```

#### Локальные модели (HuggingFace/Ollama)
```bash
EVALUATION_RAG_DELAY=0.5
EVALUATION_METRIC_DELAY=0.3
EVALUATION_EMBEDDING_DELAY=0.1
EVALUATION_LANGSMITH_DELAY=0.1
```

## Где применяются задержки

### 1. RAG запросы (`EVALUATION_RAG_DELAY`)
- При генерации ответов на каждый вопрос из датасета
- В функции `target()` в `evaluation.py`

### 2. RAGAS метрики (`EVALUATION_METRIC_DELAY`)
- При вычислении каждой из 6 метрик для каждого ответа
- Между метриками Faithfulness, AnswerCorrectness, etc.

### 3. Embeddings (`EVALUATION_EMBEDDING_DELAY`)
- При создании embeddings для метрик AnswerSimilarity, ContextRecall, ContextPrecision
- Только если используется облачный провайдер embeddings

### 4. LangSmith API (`EVALUATION_LANGSMITH_DELAY`)
- При проверке существования датасета
- При сборе результатов evaluation
- При загрузке feedback метрик

## Диагностика проблем

### Если все еще возникают ошибки:

1. **Проверьте логи**: `logs/bot.log`
2. **Увеличьте задержки**: особенно `EVALUATION_RAG_DELAY` и `EVALUATION_METRIC_DELAY`
3. **Проверьте лимиты API**: у вашего провайдера могут быть строгие ограничения
4. **Уменьшите размер датасета**: обрабатывайте меньше примеров за раз

### Примеры сообщений об ошибках:

```
Rate limit exceeded for model gpt-4o
Too many requests to OpenAI API
429: Rate limit reached for requests
```

## Оптимизация производительности

### Баланс между скоростью и стабильностью:

- **Быстрая evaluation**: задержки 0.1-0.5 сек
- **Стабильная evaluation**: задержки 1.0-2.0 сек  
- **Консервативная evaluation**: задержки 2.0+ сек

### Мониторинг:

- Включите LangSmith для отслеживания времени выполнения
- Следите за логами на предмет ошибок rate limiting
- Тестируйте с маленьким датасетом перед полной evaluation

## Отключение задержек

Если у вас нет проблем с rate limiting и нужна максимальная скорость:

```bash
EVALUATION_RAG_DELAY=0.1
EVALUATION_METRIC_DELAY=0.1
EVALUATION_EMBEDDING_DELAY=0.05
EVALUATION_LANGSMITH_DELAY=0.05
```

**Внимание**: Это может привести к ошибкам при больших датасетах или на API с строгими лимитами.