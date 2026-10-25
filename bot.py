import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

from database import add_user, init_db

# Вставь сюда свой токен, который тебе дал BotFather в Telegram
TOKEN = "8997790132:AAGNo2Lwq2IOoKsQyUWEjRRg7UQ1jSEQlr0"

# Чтобы заявки приходили вам в Telegram, вставьте свой числовой ID
# (его можно взять из лога после первой заявки). 0 — только консоль.
ADMIN_ID = 1151797411

# Тексты на кнопках
BTN_ABOUT = "ℹ️ О нас"
BTN_SERVICES = "🛠 Услуги"
BTN_CONTACTS = "📞 Контакты"
BTN_APPLY = "📝 Оставить заявку"

# Хранилище состояний FSM в памяти + диспетчер
storage = MemoryStorage()
dp = Dispatcher(storage=storage)


class Form(StatesGroup):
    """Состояния анкеты. WaitName — бот ждёт имя пользователя."""

    WaitName = State()


def main_keyboard() -> ReplyKeyboardMarkup:
    """Нижняя Reply-клавиатура."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_ABOUT), KeyboardButton(text=BTN_SERVICES)],
            [KeyboardButton(text=BTN_CONTACTS), KeyboardButton(text=BTN_APPLY)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел…",
    )


def is_menu_button(text: str | None) -> bool:
    """Проверяем, что сообщение — это нажатие одной из кнопок меню."""
    if not text:
        return False
    return any(
        key in text
        for key in ("О нас", "Услуги", "Контакты", "Оставить заявку")
    )


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
    """Приветствие и показ меню при /start."""
    await state.clear()
    user_name = html.quote(message.from_user.first_name) if message.from_user else "друг"
    await message.answer(
        f"Привет, {user_name}! 👋\n\n"
        "Я интерактивная визитка. Нажмите кнопку внизу экрана, "
        "чтобы узнать больше.",
        reply_markup=main_keyboard(),
    )


@dp.message(F.text.contains("О нас"))
async def about_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "<b>О нас</b>\n\n"
        "Мы помогаем запускать простые и понятные цифровые решения: "
        "от Telegram-ботов до сайтов-визиток.\n\n"
        "Работаем открыто, отвечаем быстро и доводим задачу до результата."
    )


@dp.message(F.text.contains("Услуги"))
async def services_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "<b>Услуги</b>\n\n"
        "• Разработка Telegram-ботов\n"
        "• Сайты-визитки и лендинги\n"
        "• Автоматизация заявок и уведомлений\n"
        "• Поддержка и доработка готовых проектов"
    )


@dp.message(F.text.contains("Контакты"))
async def contacts_handler(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        "<b>Контакты</b>\n\n"
        "📞 Телефон: +7 (900) 123-45-67\n"
        "🌐 Сайт: https://example.com\n"
        "💬 Telegram: @username"
    )


@dp.message(F.text.contains("Оставить заявку"))
async def apply_handler(message: Message, state: FSMContext) -> None:
    """Кнопка заявки: переключаем FSM в WaitName и просим имя."""
    await state.set_state(Form.WaitName)
    logging.info("Пользователь %s начал заявку", message.from_user.id if message.from_user else "?")
    await message.answer("Введите ваше имя:")


@dp.message(StateFilter(Form.WaitName), F.text)
async def save_name_handler(message: Message, state: FSMContext) -> None:
    """Пользователь прислал имя — сохраняем в SQLite и уведомляем."""
    name = (message.text or "").strip()

    # Если снова нажали кнопку меню — это не имя
    if not name or is_menu_button(name):
        await message.answer("Введите ваше имя:")
        return

    if not message.from_user:
        await message.answer("Не удалось определить ваш аккаунт. Попробуйте ещё раз.")
        return

    telegram_id = message.from_user.id
    add_user(telegram_id=telegram_id, name=name)
    await state.clear()

    logging.info("Новая заявка: telegram_id=%s, name=%s", telegram_id, name)

    await message.answer("Спасибо! Ваша заявка успешно принята!")

    # Дублируем заявку администратору в Telegram, если указан ADMIN_ID
    if ADMIN_ID:
        await message.bot.send_message(
            ADMIN_ID,
            f"Новая заявка\nID: {telegram_id}\nИмя: {html.quote(name)}",
        )


async def main() -> None:
    init_db()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
