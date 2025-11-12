import os
from typing import Dict, List

MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "20"))

_histories: Dict[int, List[dict]] = {}
_sent_ids: Dict[int, List[int]] = {}
_calories: Dict[int, List[dict]] = {}


def get_history(user_id: int) -> List[dict]:
    return _histories.get(user_id, [])


def clear_history(user_id: int) -> None:
    _histories[user_id] = []


def add_message(user_id: int, role: str, content: str) -> None:
    hist = _histories.setdefault(user_id, [])
    hist.append({"role": role, "content": content})
    if len(hist) > MAX_HISTORY_MESSAGES:
        # удаляем самые старые
        del hist[0 : len(hist) - MAX_HISTORY_MESSAGES]


def add_calorie_entry(user_id: int, entry) -> None:
    """Сохраняет запись о калориях для пользователя. entry может быть Pydantic моделью или dict."""
    lst = _calories.setdefault(user_id, [])
    try:
        # если передан Pydantic BaseModel
        data = entry.dict()
    except Exception:
        data = entry if isinstance(entry, dict) else {"kkal": getattr(entry, "kkal", None)}
    lst.append(data)


def get_calories(user_id: int) -> List[dict]:
    return _calories.get(user_id, [])


def clear_calories(user_id: int) -> None:
    _calories[user_id] = []


def add_sent_id(user_id: int, message_id: int) -> None:
    ids = _sent_ids.setdefault(user_id, [])
    ids.append(message_id)


def pop_sent_ids(user_id: int) -> List[int]:
    return _sent_ids.pop(user_id, [])


