import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
import aiohttp

from keys import API_TOKEN

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

print("Bot started")
@dp.message(Command("start"))
async def start(message: types.Message):
    greeting = (
        "Привет! Это бот команды ETF. "
        "Отправь мне файл с данными счетчиков в формате .xlsx."
    )
    await message.answer(greeting)


@dp.message(lambda msg: msg.document is not None)
async def handle_excel(message: types.Message):
    document = message.document

    if not document.file_name.lower().endswith(".xlsx"):
        await message.answer("Нужен файл в формате .xlsx")
        return

    processing_msg = await message.answer("Обрабатываю файл...")

    file = await bot.download(document.file_id)
    file_data = file.read()

    url = "https://etf-team.ru/api/volumes-info?return_resolved=true"

    await bot.send_chat_action(chat_id=message.chat.id, action="typing")
    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field(
            name='payload',
            value=file_data,
            filename=document.file_name,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

        try:
            async with session.post(url, data=form) as response:
                if response.status == 200:
                    result = await response.text()
                    await message.answer(f"Ответ:\n{result}")
                else:
                    await message.answer(f"ошибка: {response.status}")
        except Exception as e:
            await message.answer(f"Ошибка при отправке файла: {e}")
        finally:
            await processing_msg.delete()


async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
