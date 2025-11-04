import os
import logging
from typing import List, Dict
import openai
from openai import AsyncOpenAI

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m2:free")
SYSTEM_PROMPT = os.getenv(
    "SYSTEM_PROMPT", "You are a helpful personal fitness coach. Answer concisely."
)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
OPENROUTER_BASE = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

if OPENROUTER_API_KEY:
    client = AsyncOpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE
    )


async def get_response(user_id: int, user_message: str, history: List[Dict]) -> str:
    """Асинхронный запрос к OpenRouter через openai client.

    history: list[{"role": str, "content": str}]
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history + [
        {"role": "user", "content": user_message}
    ]

    if not OPENROUTER_API_KEY:
        logging.error("OPENROUTER_API_KEY is not set")
        return "Извините, конфигурация LLM не настроена."

    try:
        resp = await client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=messages,
            temperature=TEMPERATURE,
        )

        # Extract content robustly (response shape may vary)
        choice = resp.choices[0]
        # try dict-style access first
        msg = None
        try:
            msg = choice.get("message")
        except Exception:
            msg = getattr(choice, "message", None)

        if isinstance(msg, dict):
            content = msg.get("content", "")
        else:
            content = getattr(msg, "content", "") or ""

        return content.strip()
    except Exception as exc:
        logging.error("LLM request failed: key is %s, error is %s", OPENROUTER_API_KEY, exc)
        return "Извините, не могу сейчас ответить. Попробуйте позже."




