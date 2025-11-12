from aiogram import types, Dispatcher
from aiogram.filters import Command
from src.models import CalorieExtractionResult, CalorieType
from datetime import datetime, date
import logging
import json
import base64

def register_handlers(dp: Dispatcher) -> None:
    async def cmd_start(message: types.Message):
        # Удаляем предыдущие сообщения бота в чате (если есть)
        from src.storage import clear_history, pop_sent_ids

        sent_ids = pop_sent_ids(message.from_user.id)
        for mid in sent_ids:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
            except Exception:
                # не критично, продолжаем
                pass

        # Очищаем внутреннюю историю и отправляем приветствие
        clear_history(message.from_user.id)
        await message.answer("Привет! Я твой персональный тренер по фитнесу. Чем могу помочь?")

    dp.message.register(cmd_start, Command(commands=["start"]))

    async def handle_balance(message: types.Message):
        """Команда /balance — отчёт по сегодня потраченным/потреблённым калориям."""
        from src.storage import get_calories

        user_id = message.from_user.id
        entries = get_calories(user_id)
        today = datetime.utcnow().date()

        total_eat = 0
        total_burn = 0
        lines = []

        for e in entries:
            d = e.get("date")
            try:
                # date may be a string in ISO format or a date object
                if isinstance(d, str):
                    entry_date = date.fromisoformat(d)
                else:
                    entry_date = d
            except Exception:
                # skip malformed entries
                continue

            if entry_date != today:
                continue

            kkal = e.get("kkal") or e.get("kkal", 0)
            try:
                kkal = int(kkal)
            except Exception:
                continue

            c = e.get("calorie_type")
            # Normalize calorie_type which may be stored as enum value in Russian
            if c in (CalorieType.EAT.value, CalorieType.EAT.name, "EAT"):
                total_eat += kkal
                typ = "потреблено"
            elif c in (CalorieType.BURN.value, CalorieType.BURN.name, "BURN"):
                total_burn += kkal
                typ = "потрачено"
            else:
                # fallback: try simple heuristics
                sc = str(c).lower() if c is not None else ""
                if "потреб" in sc or "eat" in sc:
                    total_eat += kkal
                    typ = "потреблено"
                else:
                    total_burn += kkal
                    typ = "потрачено"

            t = e.get("time")
            if isinstance(t, str):
                time_str = t
            else:
                try:
                    time_str = t.isoformat()
                except Exception:
                    time_str = ""

            cat = e.get("category") or ""
            lines.append(f"- {time_str} — {kkal} ккал ({typ}) {cat}")
        report = f"Отчёт за {today.isoformat()}:\nПотреблено: {total_eat} ккал\nПотрачено: {total_burn} ккал\nБаланс: {total_eat - total_burn} ккал\n\n"
        if lines:
            report += "Записи:\n" + "\n".join(lines)
        else:
            report += "Записей за сегодня не найдено."

        await message.answer(report)

    dp.message.register(handle_balance, Command(commands=["balance"]))

    async def handle_message(message: types.Message):
        # обработка разных типов сообщений: текст, фото, голос
        from src.llm import (
            get_calories_from_text,
            get_calories_from_img,
            get_calories_from_voice,
        )
        from src.storage import (
            add_message,
            add_sent_id,
            get_history,
            add_calorie_entry,
        )

        user_id = message.from_user.id
        history = get_history(user_id)

        # Route by content
        if message.photo:
            # Используем подпись к фото, если есть
            img_desc = message.caption or "Фото от пользователя"
            photo = message.photo[-1]
            file_info = await message.bot.get_file(photo.file_id)
            file_buffer = await message.bot.download_file(file_info.file_path)
            image_bytes = file_buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')

            resp = await get_calories_from_img(user_id, image_base64, history)

        elif message.voice or message.audio:
            # Транскрипция не реализована — передаём подпись/placeholder
            transcript = message.caption or "Голосовое сообщение"
            
            resp = await get_calories_from_voice(user_id, transcript, history)
        else:
            text = message.text or ""
            resp = await get_calories_from_text(user_id, text, history)

        # Отправляем ответ пользователю и сохраняем историю
        sent = await message.answer(resp.answer)
        add_message(user_id, "user", message.text or (message.caption or ""))
        add_message(user_id, "assistant", resp.answer)
        try:
            add_sent_id(user_id, sent.message_id)
        except Exception:
            pass
        
        logging.info("resp : %s", str(resp))
        logging.info("resp.calories : %s", str(resp.calories))

        # Сохраняем разобранные записи калорий (если есть)
        for rec in resp.calories:
            # rec is CalorieExtractionResult instance
            try:
                add_calorie_entry(user_id, rec)
            except Exception:
                # не критично, логирование можно добавить при необходимости
                pass

    dp.message.register(handle_message)



