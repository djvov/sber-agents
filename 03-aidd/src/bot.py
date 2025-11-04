from aiogram import types, Dispatcher
from aiogram.filters import Command

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

    async def handle_text(message: types.Message):
        from src.llm import get_response
        from src.storage import add_message, add_sent_id, get_history

        user_id = message.from_user.id
        history = get_history(user_id)

        reply = await get_response(user_id, message.text, history)
        sent = await message.answer(reply)

        # Сохраняем диалог и id отправленного ботом сообщения
        add_message(user_id, "user", message.text)
        add_message(user_id, "assistant", reply)
        try:
            add_sent_id(user_id, sent.message_id)
        except Exception:
            pass

    dp.message.register(handle_text)



