import asyncio
import html
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart, CommandObject
from aiogram.types import Message, BotCommand
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "").strip()
DB_PATH = os.getenv("DB_PATH", "chat_activity.sqlite3")

router = Router()

TITLES = [
    "Главный Хуесос чата", "Легенда флуда", "Инцел/фемцел", "Пешка массонов",
    "Фашист", "Нетакуся", "sub-3", "Глава гей сообщества", "мэр г. ондон", 
    "Уебок", "Министр говна", "Адепт: ...(организация признана экстремистской, её деятельность запрещена в России)",
    "Босс хуесос", "Андрей", "Никто. Просто убейся.", "марионетка akirachan", "груша",
]
ROASTS = [
    "Пошел нахуй уебище",
    "Ты на всегда останешься девственником",
    "Скажи миру Ня пока!",
    "Тебя никто не любит",
    "Завтра ты умрешь",
    "Умри",
    "Андрей",
    "Ты никогда не добещься успеха",
    "Все твои друзья общаются с тобой из за жалости",
    "Ооо  я теперь тоже знаю где она живет спасибо любимый вместе пойдем их убивать",
]
FORTUNES = [
    "akirachan-бог чата",
    "Мир в котором ты живешь сложно назвать настоящим",
    "Андрей", 
    "Лучшая поправка-Витина отставка!",
    "ШУЕ ППШ", 
    "Для тебя это its over))))))))))))",
    "ЛАРП ЛАРП ЛАРП",
    "вика пошла нахуй",
    "Наш мир уныл",
    "make anarhia greate again", 
    "Я больше не хочу вариться в это говне",
    "Я влаженная",
    "ты чего такая злая, сексу давно что ли не было?",
]
EIGHT_BALL = [
    "Да, без сомнений.", "Похоже, что да.", "Звёзды говорят: возможно.",
    "Спроси чуть позже.", "Сейчас лучше не рассчитывать на это.",
    "Мой внутренний алгоритм сомневается.", "Ответ скрыт за завесой мемов.",
    "Определённо нет.", "Шансы есть, но не делай ставку на весь инвентарь.", "Андрей",
]
ACHIEVEMENTS = [
    (1, "Первое слово", "Ты отправил первое учтённое сообщение."),
    (50, "Разогрев", "50 сообщений — ты уже освоился."),
    (250, "Местный житель", "250 сообщений — чат начинает узнавать тебя."),
    (1000, "Легенда переписки", "1000 сообщений — солидный вклад в историю чата."),
    (1488, "Андрей" "Ты хуесос"),
    (5000, "Архивариус", "5000 сообщений — ты часть местного лора."),
]


def connect_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect_db() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS user_names (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            PRIMARY KEY (chat_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS daily_activity (
            chat_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, user_id, day)
        );
        CREATE TABLE IF NOT EXISTS hourly_activity (
            chat_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            hour INTEGER NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, day, hour)
        );
        CREATE TABLE IF NOT EXISTS chat_daily_totals (
            chat_id INTEGER NOT NULL,
            day TEXT NOT NULL,
            count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (chat_id, day)
        );
        CREATE INDEX IF NOT EXISTS idx_daily_chat_day
            ON daily_activity(chat_id, day);
        """)
        db.commit()


def now_local():
    return datetime.now().astimezone()


def is_group_message(message: Message) -> bool:
    return message.chat.type in (ChatType.GROUP, ChatType.SUPERGROUP)


def track_message(message: Message):
    if not is_group_message(message) or not message.from_user:
        return
    user = message.from_user
    if user.is_bot:
        return

    now = now_local()
    day = now.strftime("%Y-%m-%d")
    stamp = now.isoformat(timespec="seconds")
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    username = user.username or ""

    with connect_db() as db:
        db.execute("""
            INSERT INTO user_names(chat_id, user_id, username, full_name, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(chat_id, user_id) DO UPDATE SET
                username=excluded.username,
                full_name=excluded.full_name,
                last_seen=excluded.last_seen
        """, (message.chat.id, user.id, username, full_name or "Без имени", stamp))
        db.execute("""
            INSERT INTO daily_activity(chat_id, user_id, day, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id, user_id, day) DO UPDATE SET count=count+1
        """, (message.chat.id, user.id, day))
        db.execute("""
            INSERT INTO hourly_activity(chat_id, day, hour, count)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(chat_id, day, hour) DO UPDATE SET count=count+1
        """, (message.chat.id, day, now.hour))
        db.execute("""
            INSERT INTO chat_daily_totals(chat_id, day, count)
            VALUES (?, ?, 1)
            ON CONFLICT(chat_id, day) DO UPDATE SET count=count+1
        """, (message.chat.id, day))
        db.commit()


def display_name(row):
    name = row["full_name"] or "Без имени"
    if row["username"]:
        name += f" (@{row['username']})"
    return html.escape(name)


def get_top(chat_id, since_day=None, limit=10):
    with connect_db() as db:
        if since_day:
            rows = db.execute("""
                SELECT u.user_id, u.full_name, u.username, SUM(d.count) AS total
                FROM daily_activity d
                JOIN user_names u ON u.chat_id=d.chat_id AND u.user_id=d.user_id
                WHERE d.chat_id=? AND d.day>=?
                GROUP BY u.user_id
                ORDER BY total DESC, u.full_name COLLATE NOCASE ASC
                LIMIT ?
            """, (chat_id, since_day, limit)).fetchall()
        else:
            rows = db.execute("""
                SELECT u.user_id, u.full_name, u.username, SUM(d.count) AS total
                FROM daily_activity d
                JOIN user_names u ON u.chat_id=d.chat_id AND u.user_id=d.user_id
                WHERE d.chat_id=?
                GROUP BY u.user_id
                ORDER BY total DESC, u.full_name COLLATE NOCASE ASC
                LIMIT ?
            """, (chat_id, limit)).fetchall()
    return rows


def get_count_for_user(chat_id, user_id, since_day=None):
    with connect_db() as db:
        if since_day:
            row = db.execute("""
                SELECT COALESCE(SUM(count), 0) AS total FROM daily_activity
                WHERE chat_id=? AND user_id=? AND day>=?
            """, (chat_id, user_id, since_day)).fetchone()
        else:
            row = db.execute("""
                SELECT COALESCE(SUM(count), 0) AS total FROM daily_activity
                WHERE chat_id=? AND user_id=?
            """, (chat_id, user_id)).fetchone()
    return int(row["total"])


def get_known_users(chat_id):
    with connect_db() as db:
        return db.execute("""
            SELECT user_id, full_name, username FROM user_names
            WHERE chat_id=? ORDER BY user_id
        """, (chat_id,)).fetchall()


def fmt_top(rows, title):
    if not rows:
        return f"<b>{title}</b>\nПока недостаточно данных. Напишите несколько сообщений!"
    lines = [f"<b>{title}</b>"]
    medals = ["🥇", "🥈", "🥉"]
    for i, row in enumerate(rows, 1):
        medal = medals[i - 1] if i <= 3 else f"{i}."
        lines.append(f"{medal} {display_name(row)} — <b>{row['total']}</b>")
    return "\n".join(lines)


def target_name(message: Message):
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        name = " ".join(x for x in [user.first_name, user.last_name] if x).strip() or "Без имени"
        return user.id, html.escape(name), user.username
    if message.from_user:
        user = message.from_user
        name = " ".join(x for x in [user.first_name, user.last_name] if x).strip() or "Без имени"
        return user.id, html.escape(name), user.username
    return None, "Неизвестный участник", None


@router.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Я считаю активность в группах и умею развлекать чат 😎\n\n"
        "<b>Статистика</b>\n"
        "/top — топ за всё время\n/topday — топ за сегодня\n"
        "/topweek — топ за 7 дней\n/me — твоя статистика\n"
        "/stats — статистика чата\n/activity — активность по часам\n\n"
        "<b>Развлечения</b>\n"
        "/title — случайный титул\n/coin — монетка\n/dice — кубик\n"
        "/ball — магический шар\n/choose чай | кофе — выбрать вариант\n"
        "/fortune — предсказание\n/roast — шуточная подколка (можно ответить на сообщение)\n"
        "/ship — случайный шуточный шип\n/duel — сравнить активность (ответь на сообщение)\n"
        "/achievements — твои достижения\n/help — эта справка",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def help_command(message: Message):
    await start(message)


@router.message(Command("top"))
async def top_all(message: Message):
    if not is_group_message(message):
        await message.answer("Эту команду нужно вызвать внутри группы.")
        return
    await message.answer(fmt_top(get_top(message.chat.id), "🏆 Топ участников за всё время"), parse_mode="HTML")


@router.message(Command("topday"))
async def top_day(message: Message):
    if not is_group_message(message):
        await message.answer("Эту команду нужно вызвать внутри группы.")
        return
    today = now_local().strftime("%Y-%m-%d")
    await message.answer(fmt_top(get_top(message.chat.id, today), "📅 Топ участников за сегодня"), parse_mode="HTML")


@router.message(Command("topweek"))
async def top_week(message: Message):
    if not is_group_message(message):
        await message.answer("Эту команду нужно вызвать внутри группы.")
        return
    since = (now_local().date() - timedelta(days=6)).strftime("%Y-%m-%d")
    await message.answer(fmt_top(get_top(message.chat.id, since), "📈 Топ участников за последние 7 дней"), parse_mode="HTML")


@router.message(Command("me"))
async def my_stats(message: Message):
    if not is_group_message(message) or not message.from_user:
        await message.answer("Вызови /me внутри группы, чтобы увидеть свою статистику.")
        return
    user_id = message.from_user.id
    today = now_local().strftime("%Y-%m-%d")
    all_time = get_count_for_user(message.chat.id, user_id)
    today_count = get_count_for_user(message.chat.id, user_id, today)
    since = (now_local().date() - timedelta(days=6)).strftime("%Y-%m-%d")
    week_count = get_count_for_user(message.chat.id, user_id, since)
    with connect_db() as db:
        rank_row = db.execute("""
            WITH totals AS (
                SELECT user_id, SUM(count) AS total
                FROM daily_activity WHERE chat_id=? GROUP BY user_id
            )
            SELECT 1 + (SELECT COUNT(*) FROM totals WHERE total > COALESCE(
                (SELECT total FROM totals WHERE user_id=?), 0
            )) AS rank
        """, (message.chat.id, user_id)).fetchone()
    rank = rank_row["rank"] if all_time else "—"
    await message.answer(
        f"👤 <b>Твоя статистика</b>\nСообщений за всё время: <b>{all_time}</b>\n"
        f"За сегодня: <b>{today_count}</b>\nЗа 7 дней: <b>{week_count}</b>\n"
        f"Место в общем топе: <b>{rank}</b>", parse_mode="HTML"
    )


@router.message(Command("stats"))
async def stats(message: Message):
    if not is_group_message(message):
        await message.answer("Эту команду нужно вызвать внутри группы.")
        return
    today = now_local().strftime("%Y-%m-%d")
    since = (now_local().date() - timedelta(days=6)).strftime("%Y-%m-%d")
    with connect_db() as db:
        total = db.execute("SELECT COALESCE(SUM(count),0) AS n FROM chat_daily_totals WHERE chat_id=?", (message.chat.id,)).fetchone()["n"]
        today_total = db.execute("SELECT COALESCE(SUM(count),0) AS n FROM chat_daily_totals WHERE chat_id=? AND day=?", (message.chat.id, today)).fetchone()["n"]
        week_total = db.execute("SELECT COALESCE(SUM(count),0) AS n FROM chat_daily_totals WHERE chat_id=? AND day>=?", (message.chat.id, since)).fetchone()["n"]
        users = db.execute("SELECT COUNT(*) AS n FROM user_names WHERE chat_id=?", (message.chat.id,)).fetchone()["n"]
    await message.answer(
        f"📊 <b>Статистика чата</b>\nСообщений за всё время сбора: <b>{total}</b>\n"
        f"За сегодня: <b>{today_total}</b>\nЗа последние 7 дней: <b>{week_total}</b>\n"
        f"Участников, писавших сообщения: <b>{users}</b>", parse_mode="HTML"
    )


@router.message(Command("activity"))
async def activity(message: Message):
    if not is_group_message(message):
        await message.answer("Эту команду нужно вызвать внутри группы.")
        return
    today = now_local().strftime("%Y-%m-%d")
    with connect_db() as db:
        rows = db.execute("SELECT hour, count FROM hourly_activity WHERE chat_id=? AND day=? ORDER BY hour", (message.chat.id, today)).fetchall()
    if not rows:
        await message.answer("Сегодня пока нет собранной статистики активности.")
        return
    values = {int(row["hour"]): int(row["count"]) for row in rows}
    peak = max(values.values())
    lines = ["🕒 <b>Активность по часам за сегодня</b>"]
    for hour in range(24):
        count = values.get(hour, 0)
        bars = "▰" * min(20, round(count / peak * 20)) if peak else ""
        lines.append(f"{hour:02d}:00 {bars} {count}")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("title"))
async def title_command(message: Message):
    _, name, _ = target_name(message)
    await message.answer(f"🎖 {name}, твой титул сегодня: <b>{html.escape(random.choice(TITLES))}</b>", parse_mode="HTML")


@router.message(Command("coin"))
async def coin(message: Message):
    await message.answer("🪙 Выпало: <b>" + random.choice(["Орёл", "Решка"]) + "</b>!", parse_mode="HTML")


@router.message(Command("dice"))
async def dice(message: Message):
    value = random.randint(1, 6)
    faces = {1: "⚀", 2: "⚁", 3: "⚂", 4: "⚃", 5: "⚄", 6: "⚅"}
    await message.answer(f"🎲 {faces[value]} Выпало число <b>{value}</b>!", parse_mode="HTML")


@router.message(Command("ball"))
async def ball(message: Message, command: CommandObject):
    question = (command.args or "").strip()
    if not question:
        await message.answer("Задай вопрос после команды, например: <code>/ball получится ли у меня?</code>", parse_mode="HTML")
        return
    await message.answer("🔮 " + random.choice(EIGHT_BALL))


@router.message(Command("choose"))
async def choose(message: Message, command: CommandObject):
    raw = (command.args or "").strip()
    options = [x.strip() for x in raw.split("|") if x.strip()]
    if len(options) < 2:
        await message.answer("Напиши хотя бы два варианта через |.\nПример: <code>/choose чай | кофе</code>", parse_mode="HTML")
        return
    if len(options) > 10:
        await message.answer("Давай не больше 10 вариантов за раз 🙂")
        return
    await message.answer("🤔 Я выбираю: <b>" + html.escape(random.choice(options)) + "</b>", parse_mode="HTML")


@router.message(Command("fortune"))
async def fortune(message: Message):
    _, name, _ = target_name(message)
    await message.answer(f"🔮 Предсказание для {name}:\n{html.escape(random.choice(FORTUNES))}", parse_mode="HTML")


@router.message(Command("roast"))
async def roast(message: Message):
    _, name, _ = target_name(message)
    await message.answer(f"🔥 {name} {random.choice(ROASTS)}. А еще ты лох по жизни", parse_mode="HTML")


@router.message(Command("ship"))
async def ship(message: Message):
    if not is_group_message(message):
        await message.answer("Команда работает в группе.")
        return
    users = get_known_users(message.chat.id)
    if message.reply_to_message and message.reply_to_message.from_user and message.from_user:
        first = message.from_user
        second = message.reply_to_message.from_user
        if first.id == second.id:
            await message.answer("Ты неудачник")
            return
        names = [
            " ".join(x for x in [first.first_name, first.last_name] if x).strip() or "Участник 1",
            " ".join(x for x in [second.first_name, second.last_name] if x).strip() or "Участник 2",
        ]
    else:
        if len(users) < 2:
            await message.answer("Пока мало участников в статистике. Или ответь на сообщение человека командой /ship.")
            return
        picked = random.sample(list(users), 2)
        names = [row["full_name"] for row in picked]
    score = random.randint(0, 100)
    bar = "❤️" * (score // 10) + "🖤" * (10 - score // 10)
    await message.answer(
        f"💞 <b>Шуточный шипометр</b>\n{html.escape(names[0])} × {html.escape(names[1])}\n"
        f"{bar}\nСовместимость по версии бота: <b>{score}%</b>\n<i>Это случайное число, не настоящий вывод о людях.</i>",
        parse_mode="HTML"
    )


@router.message(Command("duel"))
async def duel(message: Message):
    if not is_group_message(message) or not message.from_user:
        await message.answer("Вызови /duel ответом на сообщение другого участника в группе.")
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer("Ответь командой /duel на сообщение соперника.")
        return
    first = message.from_user
    second = message.reply_to_message.from_user
    if first.id == second.id:
        await message.answer("Нужно выбрать другого соперника 😄")
        return
    a = get_count_for_user(message.chat.id, first.id)
    b = get_count_for_user(message.chat.id, second.id)
    n1 = html.escape(" ".join(x for x in [first.first_name, first.last_name] if x).strip() or "Игрок 1")
    n2 = html.escape(" ".join(x for x in [second.first_name, second.last_name] if x).strip() or "Игрок 2")
    if a == b:
        result = "Ничья! Силы равны."
    else:
        winner = n1 if a > b else n2
        result = f"🏆 Сейчас лидирует {winner}!"
    await message.answer(f"⚔️ <b>Дуэль активности</b>\n{n1}: {a} сообщений\n{n2}: {b} сообщений\n{result}", parse_mode="HTML")


@router.message(Command("achievements"))
async def achievements(message: Message):
    if not is_group_message(message) or not message.from_user:
        await message.answer("Вызови /achievements внутри группы.")
        return
    count = get_count_for_user(message.chat.id, message.from_user.id)
    earned = [item for item in ACHIEVEMENTS if count >= item[0]]
    if not earned:
        await message.answer("🏅 Пока нет достижений. Напиши несколько сообщений — и начнётся путь!")
        return
    lines = ["🏅 <b>Твои достижения</b>"]
    for threshold, name, description in earned:
        lines.append(f"✅ <b>{name}</b> — {html.escape(description)}")
    next_item = next((item for item in ACHIEVEMENTS if count < item[0]), None)
    if next_item:
        lines.append(f"\nДо следующего достижения «{next_item[1]}» осталось: <b>{next_item[0] - count}</b> сообщений.")
    else:
        lines.append("\nТы открыл все достижения этой версии!")
    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message()
async def count_every_message(message: Message):
    # Сохраняем агрегированные счётчики, а не содержание сообщений.
    track_message(message)


async def main():
    if not TOKEN:
        raise RuntimeError("Не найден BOT_TOKEN. Задай его в .env или через переменную окружения CMD.")
    init_db()
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await bot.set_my_commands([
        BotCommand(command="top", description="Топ за всё время"),
        BotCommand(command="topday", description="Топ за сегодня"),
        BotCommand(command="topweek", description="Топ за 7 дней"),
        BotCommand(command="me", description="Моя статистика"),
        BotCommand(command="stats", description="Статистика чата"),
        BotCommand(command="activity", description="Активность по часам"),
        BotCommand(command="title", description="Случайный титул"),
        BotCommand(command="coin", description="Подбросить монетку"),
        BotCommand(command="dice", description="Бросить кубик"),
        BotCommand(command="ball", description="Ответ магического шара"),
        BotCommand(command="choose", description="Выбрать вариант"),
        BotCommand(command="fortune", description="Предсказание дня"),
        BotCommand(command="roast", description="Безобидная подколка"),
        BotCommand(command="ship", description="Шуточный шипометр"),
        BotCommand(command="duel", description="Дуэль активности"),
        BotCommand(command="achievements", description="Мои достижения"),
        BotCommand(command="help", description="Список команд"),
    ])
    print("Бот запущен. Для остановки нажми Ctrl+C.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Бот остановлен.")
