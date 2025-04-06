from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaDocument
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiohttp
import asyncio
import datetime

from db import init_db, add_user, get_all_users
from keys import API_TOKEN, SAD_PIC_FILE_ID, HELLO_PIC_FILE_ID, TEST_FILE_PATH, HA_PIC_FILE_ID

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

class Form(StatesGroup):
    waiting_for_voltage = State()
    waiting_for_contract = State()
    waiting_for_max_voltage = State()

def manual_input_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="У меня нет файла", callback_data="manual_input")]
    ])

def confirm_test_file_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Да!", callback_data="send_test_file")]
    ])

def voltage_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="ВН", callback_data="BH"),
            InlineKeyboardButton(text="СН1", callback_data="CH1")
        ],
        [
            InlineKeyboardButton(text="СН11", callback_data="CH11"),
            InlineKeyboardButton(text="НН", callback_data="HH")
        ]
    ])


def contract_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Купли-продажи", callback_data="contract_false"),
            InlineKeyboardButton(text="Энергоснабжения", callback_data="contract_true")
        ]
    ])

@dp.message(Command("start"))
async def start(message: types.Message):
    is_new_user = await add_user(message.from_user.id, message.from_user.username or "unknown")
    greeting = (
        "Мы разработали сервис, который помогает юридическим лицам быстро и точно подобрать оптимальный тариф на электроэнергию, основываясь на данных потребления."
        "\n\n📂 Отправь Excel-файл с показаниями счетчиков (формат .xlsx), и мы:"
        "\n— автоматически проанализируем потребление по часам,"
        "\n— определим пиковые нагрузки,"
        "\n— и предложим наиболее выгодную тарифную категорию."
        "\n\n📲 Если у вас нет файла, мы подготовили тестовый файл, который можно использовать в качестве примера. Просто нажмите кнопку ниже, и проверьте наш сервис!"
        "\n\n🔍 Наш сервис работает быстро и понятно — без сложных расчетов, графиков и бюрократии. Поможем сократить принятие решений с нескольких дней до пары минут."
    )
    sent_message = await message.answer_photo(
        HELLO_PIC_FILE_ID,
        caption=greeting,
        reply_markup=manual_input_keyboard()
    )
    if is_new_user:
        try:
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=sent_message.message_id)
        except Exception as e:
            print(f"Не удалось закрепить сообщение: {e}")

@dp.message(lambda msg: msg.document is not None)
async def handle_excel(message: types.Message, state: FSMContext):
    document = message.document

    if not document.file_name.lower().endswith(".xlsx"):
        await message.answer("Нужен файл в формате .xlsx")
        return

    processing_msg = await message.answer("Обрабатываю файл...")

    file = await bot.download(document.file_id)
    file_data = file.read()


    await state.update_data(file_data=file_data, filename=document.file_name)

    await message.answer("Какое у вас напряжение?", reply_markup=voltage_keyboard())
    await state.set_state(Form.waiting_for_voltage)
    await processing_msg.delete()

@dp.callback_query(Form.waiting_for_voltage, F.data.in_(["BH", "СН1", "СН11", "НН"]))
async def process_voltage(callback: CallbackQuery, state: FSMContext):
    voltage = callback.data
    await state.update_data(voltage_category=voltage)

    await callback.message.edit_text("Какой договор вы заключаете?", reply_markup=contract_keyboard())
    await state.set_state(Form.waiting_for_contract)
    await callback.answer()

@dp.callback_query(Form.waiting_for_contract, F.data.in_(["contract_false", "contract_true"]))
async def process_contract(callback: CallbackQuery, state: FSMContext):
    contract_data = callback.data
    contract = True if contract_data == "contract_true" else False
    await state.update_data(contract_type=contract)
    await callback.message.edit_text("Какое максимальное напряжение? Введите числовое значение.")
    await state.set_state(Form.waiting_for_max_voltage)
    await callback.answer()


@dp.message(Form.waiting_for_max_voltage)
async def process_max_voltage(message: types.Message, state: FSMContext):
    try:
        max_voltage = int(float(message.text))
    except ValueError:
        await message.answer("Введите корректное числовое значение (целое число).")
        return

    await state.update_data(max_voltage=max_voltage)

    data = await state.get_data()
    file_data = data["file_data"]
    filename = data["filename"]
    voltage_category = data["voltage_category"]
    contract_type = data["contract_type"]

    contract_str = "true" if contract_type else "false"

    url = (
        f"https://etf-team.ru/api/clients/cases?"
        f"is_transmission_included={contract_str}&"
        f"max_power_capacity_kwt={max_voltage}&"
        f"voltage_category={voltage_category}"
    )

    processing_msg = await message.answer("Отправляю данные на сервер...")

    async with aiohttp.ClientSession() as session:
        form = aiohttp.FormData()
        form.add_field(
            name='payload',
            value=file_data,
            filename=filename,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        headers = {"accept": "application/json"}

        async with session.post(url, data=form, headers=headers) as resp:
            text = await resp.text()
            print(resp.status)
            if resp.status == 200 or 201:
                await message.answer(f"✅ Успех! Ответ сервера:\n{text}")
            elif resp.status == 500 or 400:
                await message.answer_photo(
                    SAD_PIC_FILE_ID,
                    caption=(f"Ошибка {resp.status} при отправке:\n{text}")
                )

    await processing_msg.delete()
    await state.clear()


@dp.callback_query(F.data == "manual_input")
async def manual_input_prompt(callback: CallbackQuery):
    a = ("Хочешь протестировать наш сервис на примере тестового Excel-файла?")
    await callback.message.answer_photo(HA_PIC_FILE_ID, caption=a, reply_markup=confirm_test_file_keyboard())

    await callback.answer()

@dp.callback_query(F.data == "send_test_file")
async def send_test_file(callback: CallbackQuery):
    try:
        await callback.message.edit_media(
            media=InputMediaDocument(
                media=types.FSInputFile(TEST_FILE_PATH),
                caption="Вот пример тестового файла, который я сейчас отправлю на сервер"
            )
        )
    except Exception as e:
        await callback.message.answer_photo(SAD_PIC_FILE_ID, caption=f"Ошибка при отправке файла пользователю: {e}")
        await callback.answer()
        return

    await asyncio.sleep(1)
    await bot.send_chat_action(chat_id=callback.message.chat.id, action="typing")
    processing_msg = await callback.message.answer("Отправляю тестовый файл и жду ответа сервера...")

    url = "https://etf-team.ru/api/volumes-info?return_resolved=true"
    try:
        with open(TEST_FILE_PATH, "rb") as f:
            file_data = f.read()
        async with aiohttp.ClientSession() as session:
            form = aiohttp.FormData()
            form.add_field(
                name='payload',
                value=file_data,
                filename="test_file.xlsx",
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            async with session.post(url, data=form) as response:
                if response.status == 200:
                    result = await response.text()
                    await callback.message.answer(f"Ответ сервера на тестовый файл:\n{result}")
                else:
                    bad = (
                        f"Что-то пошло не так! :( \n\nНаш администратор уже уведомлен об ошибке и мы ее обязательно изучим! "
                        f"\nПопробуйте ввести данные ещё раз. \nКод ошибки: {response.status}")
                    await callback.message.answer_photo(SAD_PIC_FILE_ID, caption=bad)
    except Exception as e:
        await callback.message.answer_photo(SAD_PIC_FILE_ID, caption=f"Ошибка при отправке файла: {e}")
    finally:
        await processing_msg.delete()
        await callback.answer()

async def reminder():
    while True:
        now = datetime.datetime.now()
        if now.day == 15:
            user_ids = await get_all_users()
            for user_id in user_ids:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text="Доброго времени суток!\nНапоминаем, что необходимо обновить данные с счетчиков для получения актуальных тарифов. Обновите пожалуйста информацию по счетчикам."
                    )
                except Exception as e:
                    print(f"error to send message {user_id}")
        await asyncio.sleep(48 * 60 * 60)


async def main():
    await init_db()

    asyncio.create_task(reminder())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
