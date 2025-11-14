import os
import json
import logging
import asyncio
import inspect
import ollama 
from ollama import AsyncClient

from typing import List, Dict, Optional, Any

from src.models import CalorieResponse

logger = logging.getLogger(__name__)


async def _load_prompt_file(name: str) -> str:
    """
    Load prompt text from prompts/<name>.txt relative to project root.
    Falls back to empty string if file not found or on error.
    """
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    path = os.path.normpath(os.path.join(base_dir, "prompts", f"{name}.txt"))
    try:
        def _read() -> str:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        return await asyncio.to_thread(_read)
    except Exception:
        logger.debug("Prompt file not found or unreadable: %s", path)
        return _get_env("SYSTEM_PROMPT", "") or ""


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(name, default)


def _build_prompt(system_prompt: str, history: List[Dict[str, Any]], user_message: str) -> str:
    """
    Формируем текстовый промпт для модели на основе системного промпта,
    истории и нового сообщения пользователя.
    """
    parts: List[str] = []
    if system_prompt:
        parts.append(system_prompt.strip())
    for msg in history:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        parts.append(f"{role.upper()}: {content}")
    parts.append(f"USER: {user_message}")
    """parts.append(
        "IMPORTANT: Return only a single valid JSON object matching the schema:\n"
        '{ "calories": [ { "date": "YYYY-MM-DD", "time": "HH:MM:SS", '
        '"calorie_type": "EAT"|"BURN", "kkal": 123, "category": "..." } ], '
        '"answer": "..." }\n'
        "Do not include any extra text outside the JSON."
    )"""
    return "\n\n".join(parts)


def _extract_json_fragment(text: str) -> Optional[str]:
    """
    Попытаться вырезать JSON-объект из произвольного текста:
    находим первую '{' и последнюю '}' и возвращаем подстроку.
    """
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return None


async def _call_ollama_lib(model: str, prompt: str, temperature: float) -> str:
    """
    Вызывать python-библиотеку `ollama`. Блокирующие вызовы выполняются в отдельном потоке.
    Если библиотека отсутствует или её интерфейс не поддерживается — возбуждаем исключение.
    Никаких HTTP/fallback вызовов не выполняется.
    """ 
    client = AsyncClient()
            
    out = await client.chat(model=model, messages=[{"role": "user", "content": prompt}])  # type: ignore
                   
    return out['message']['content']
                    


async def _parse_response(text: str) -> CalorieResponse:
    """
    Парсим текст ответа модели в `CalorieResponse`. Если не получается,
    пробуем извлечь JSON-фрагмент. В случае неуспеха возвращаем безопасный fallback.
    """
    try:
        data = json.loads(text)
    except Exception:
        fragment = _extract_json_fragment(text)
        if fragment:
            try:
                data = json.loads(fragment)
            except Exception:
                logger.error("Failed to parse JSON fragment from model response", exc_info=True)
                return CalorieResponse(calories=[], answer="Не удалось распознать данные. Попробуйте переформулировать.")
        else:
            logger.error("No JSON found in model response")
            return CalorieResponse(calories=[], answer="Не удалось распознать данные. Попробуйте переформулировать.")

    try:
        resp = CalorieResponse.model_validate(data)
        return resp
    except Exception:
        logger.error("Parsed JSON does not match CalorieResponse schema", exc_info=True)
        return CalorieResponse(calories=[], answer="Не удалось распознать структуру данных. Попробуйте переформулировать.")


async def _call_model_and_parse(model: str, prompt: str, temperature: float) -> CalorieResponse:
    raw = await _call_ollama_lib(model, prompt, temperature)
    raw = raw.replace('```json', '').replace('```', '').replace('EAAT', 'EAT').strip()
    logging.info("raw: %s", raw)
    return await _parse_response(raw)


async def get_calories_from_text(user_id: int, text: str, history: List[Dict[str, Any]]) -> CalorieResponse:
    # Load prompt template from prompts/text.txt (fallback to SYSTEM_PROMPT)
    system_prompt = await _load_prompt_file("text")
    model = _get_env("OLLAMA_MODEL", "qwen3:8b") or "qwen3:8b"
    temperature = float(_get_env("TEMPERATURE", "0.7") or 0.7)
    prompt = _build_prompt(system_prompt, history or [], text or "")
    logger.info("Calling Ollama for text (user_id=%s, model=%s)", user_id, model)
    return await _call_model_and_parse(model, prompt, temperature)


async def get_calories_from_img(user_id: int, image_base64: str, history: List[Dict[str, Any]]) -> CalorieResponse:
    # Load prompt template from prompts/img.txt (fallback to IMAGE_PROMPT or SYSTEM_PROMPT)
    image_prompt = await _load_prompt_file("img") or _get_env("IMAGE_PROMPT") or _get_env("SYSTEM_PROMPT", "") or ""
    model = _get_env("IMAGE_MODEL", "qwen3:8b") or "qwen3:8b"
    temperature = float(_get_env("TEMPERATURE", "0.7") or 0.7)
    user_msg = f"Image (base64): {image_base64[:200]}..."
    prompt = _build_prompt(image_prompt, history or [], user_msg)
    logger.info("Calling Ollama for image (user_id=%s, model=%s)", user_id, model)
    return await _call_model_and_parse(model, prompt, temperature)


async def get_calories_from_voice(user_id: int, transcript: str, history: List[Dict[str, Any]]) -> CalorieResponse:
    # Load prompt template from prompts/audio.txt (fallback to AUDIO_PROMPT or SYSTEM_PROMPT)
    audio_prompt = await _load_prompt_file("audio") or _get_env("AUDIO_PROMPT") or _get_env("SYSTEM_PROMPT", "") or ""
    model = _get_env("AUDIO_MODEL", "qwen3:8b") or "qwen3:8b"
    temperature = float(_get_env("TEMPERATURE", "0.7") or 0.7)
    prompt = _build_prompt(audio_prompt, history or [], transcript or "")
    logger.info("Calling Ollama for voice (user_id=%s, model=%s)", user_id, model)
    return await _call_model_and_parse(model, prompt, temperature)
 