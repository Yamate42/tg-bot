import asyncio
import logging
import os
import sqlite3
import sys
from pathlib import Path

from aiohttp import web
from aiogram import Bot, Dispatcher, F, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup

# Токен BotFather. На Render можно задать переменную BOT_TOKEN — она важнее.
TOKEN = os.environ.get("BOT_TOKEN", "8997790132:AAGNo2Lwq2IOoKsQyUWEjRRg7UQ1jSEQlr0")

# Заявки дублируются этому Telegram ID
ADMIN_ID = 1151797411

# SQLite рядом с bot.py (на Render диск временный, после рестарта база может очиститься)
DB_PATH = Path(__file__).with_name("database.db")

BTN_ABOUT = "ℹ️ О нас"
BTN_SERVICES = "🛠 Услуги"
BTN_CONTACTS = "📞 Контакты"
BTN_APPLY = "📝 Оставить заявку"

storage = MemoryStorage()
dp = Dispatcher(storage=storage)


def init_db() -> None:
    """Создаёт таблицу users, если её ещё нет."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_user(telegram_id: int, name: str) -> None:
    """Сохраняет заявку. Повторная заявка того же пользователя обновляет имя."""
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO users (telegram_id, name)
            VALUES (?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET name = excluded.name
            """,
            (telegram_id, name.strip()),
        )
        conn.commit()


class Form(StatesGroup):
    """WaitName — бот ждёт имя пользователя."""

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
    if not text:
        return False
    return any(key in text for key in ("О нас", "Услуги", "Контакты", "Оставить заявку"))


@dp.message(CommandStart())
async def command_start_handler(message: Message, state: FSMContext) -> None:
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
    await state.set_state(Form.WaitName)
    logging.info("Пользователь %s начал заявку", message.from_user.id if message.from_user else "?")
    await message.answer("Введите ваше имя:")


@dp.message(StateFilter(Form.WaitName), F.text)
async def save_name_handler(message: Message, state: FSMContext) -> None:
    name = (message.text or "").strip()

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

    if ADMIN_ID:
        await message.bot.send_message(
            ADMIN_ID,
            f"Новая заявка\nID: {telegram_id}\nИмя: {html.quote(name)}",
        )


async def health(_request: web.Request) -> web.Response:
    """Ответ для проверки Render: сервис слушает HTTP-порт."""
    return web.Response(text="OK")


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    port = int(os.environ.get("PORT", 10000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logging.info("HTTP-сервер слушает 0.0.0.0:%s", port)
    return runner


async def main() -> None:
    init_db()
    runner = await start_web_server()
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    try:
        await dp.start_polling(bot, drop_pending_updates=True)
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
