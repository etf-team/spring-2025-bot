import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
import aiohttp
from aiogram.types import FSInputFile


from db import init_db, add_user
from keys import API_TOKEN

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class ManualInputStates(StatesGroup):
    waiting_for_kwh = State()
    waiting_for_voltage = State()

print("Bot started")

def manual_input_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Ввести вручную", callback_data="manual_input")]
    ])

def voltage_selection_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Высокое", callback_data="voltage_high")],
        [InlineKeyboardButton(text="Средне", callback_data="voltage_medium")],
        [InlineKeyboardButton(text="Среднее 2", callback_data="voltage_medium2")],
        [InlineKeyboardButton(text="Низкое", callback_data="voltage_low")],
    ])



@dp.message(Command("start"))
async def start(message: types.Message):
    await add_user(message.from_user.id, message.from_user.username or "unknown")
    greeting = (f' Мы разработали сервис, который помогает юридическим лицам быстро и точно подобрать оптимальный тариф на электроэнергию, основываясь на данных потребления.'
                f' \n\n📂 Отправь Excel-файл с показаниями счетчиков (формат .xlsx), и мы:'
                f'\n— автоматически проанализируем потребление по часам,'
                f'\n— определим пиковые нагрузки,'
                f'\n— и предложим наиболее выгодную тарифную категорию.'
                f'\n\n📲 Или выбери ручной ввод, если таблиц под рукой пока нет.'
                f'\n\n🔍 Наш сервис работает быстро и понятно — без сложных расчетов, графиков и бюрократии. Поможем сократить принятие решений с нескольких дней до пары минут.'
    )

    photo = FSInputFile("./static/hello_pic.png")
    await message.answer_photo(photo, caption=greeting, reply_markup=manual_input_keyboard())



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


@dp.callback_query(F.data == "manual_input")
async def manual_input(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите количество потреблённой электроэнергии (в кВт·ч):")
    await state.set_state(ManualInputStates.waiting_for_kwh)
    await callback.answer()


@dp.message(ManualInputStates.waiting_for_kwh)
async def received_kwh(message: types.Message, state: FSMContext):
    try:
        kwh = float(message.text)
        await state.update_data(kwh=kwh)
        await message.answer("Выберите ваше напряжение:", reply_markup=voltage_selection_keyboard())
        await state.set_state(ManualInputStates.waiting_for_voltage)
    except ValueError:
        await message.answer("Пожалуйста, введите корректное число (например, 150.5)")


@dp.callback_query(ManualInputStates.waiting_for_voltage)
async def voltage_selected(callback: CallbackQuery, state: FSMContext):
    voltage_map = {
        "voltage_high": 1,
        "voltage_medium": 2,
        "voltage_medium2": 3,
        "voltage_low": 4
    }

    voltage_code = callback.data
    voltage = voltage_map.get(voltage_code)

    if not voltage:
        await callback.answer("Неизвестный вариант", show_alert=True)
        return

    data = await state.get_data()
    kwh = data.get("kwh")

    payload = {
        "kwh": kwh,
        "voltage": voltage
    }
    print(payload)

    url = "https://etf-team.ru/api/volumes-info?return_resolved=true"

    await bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    result = await response.text()
                    await callback.message.edit_text(f"Ответ:\n{result}")
                else:
                    bad = f"Что-то пошло не так! :( \nНаш администратор уже уведомлен об ошибке и мы ее обязательно изучим! \nПопробуйте ввести данные ещё раз. \nКод ошибки: {response.status}"
                    photo = FSInputFile("./static/sad.png")
                    await callback.message.answer_photo(photo, caption=bad)

        except Exception as e:
            await callback.message.edit_text(f"Ошибка при отправке: {e}")
        finally:
            await state.clear()
            await callback.answer()



async def main():
    await init_db()
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())
