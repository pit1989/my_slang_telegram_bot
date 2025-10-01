
import telebot
import sqlite3
from telebot import types

API_TOKEN = "YOUR_BOT_TOKEN_HERE"  # вставь сюда свой токен
bot = telebot.TeleBot(API_TOKEN)

DB_PATH = "slang.db"
ALLOWED_CATEGORIES = ["айти", "геймерский", "молодёжный", "общий"]

# --- Настройки доступа ---
ADMIN_ONLY = True
ADMINS = [123456789, YOUR_USER_ID_HERE]  # сюда вставь свой Telegram user_id

# --- Инициализация базы ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    # Основная база слов
    cur.execute('''
        CREATE TABLE IF NOT EXISTS slang (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            definition TEXT,
            category TEXT,
            UNIQUE(word, category)
        )
    ''')
    # Таблица предложений пользователей
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pending_words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT,
            definition TEXT,
            category TEXT,
            user_id INTEGER
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- Работа с базой ---
def get_definitions(word):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT definition, category FROM slang WHERE word = ?", (word.lower(),))
    results = cur.fetchall()
    conn.close()
    return results if results else None

def add_word(word, definition, category):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO slang (word, definition, category) VALUES (?, ?, ?)",
                    (word.lower(), definition, category))
        conn.commit()
        ok = True
    except sqlite3.IntegrityError:
        ok = False
    conn.close()
    return ok

def add_pending(word, definition, category, user_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("INSERT INTO pending_words (word, definition, category, user_id) VALUES (?, ?, ?, ?)",
                (word.lower(), definition, category, user_id))
    conn.commit()
    conn.close()

def get_pending():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, word, definition, category, user_id FROM pending_words")
    results = cur.fetchall()
    conn.close()
    return results

def approve_word(pending_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT word, definition, category FROM pending_words WHERE id = ?", (pending_id,))
    result = cur.fetchone()
    if result:
        word, definition, category = result
        add_word(word, definition, category)
        cur.execute("DELETE FROM pending_words WHERE id = ?", (pending_id,))
        conn.commit()
    conn.close()

def reject_word(pending_id):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM pending_words WHERE id = ?", (pending_id,))
    conn.commit()
    conn.close()

# --- Состояния пользователей ---
user_states = {}

# --- Команды ---
@bot.message_handler(commands=["start", "help"])
def start(message):
    uid = message.from_user.id
    if uid in ADMINS:
        txt = (
            "Привет, админ! 👑\n\n"
            "Ты можешь добавлять слова сразу, одобрять предложения пользователей и просматривать всё.\n\n"
            "Команды:\n"
            "/list <категория> — показать все слова в категории\n"
            "/pending — список предложенных слов\n"
            "/approve <id> — одобрить предложение\n"
            "/reject <id> — отклонить предложение\n"
            "/cancel — отменить текущее действие"
        )
    else:
        txt = (
            "Привет! Я словарь сленга 🤖\n\n"
            "Ты можешь:\n"
            "— узнать определение слова\n"
            "— предложить новое слово (оно попадёт к администратору)\n"
            "— посмотреть слова в категориях\n\n"
            "Категории: " + ", ".join(ALLOWED_CATEGORIES) + "\n"
            "Команды:\n"
            "/list <категория> — показать все слова в категории\n"
            "/cancel — отменить текущее действие"
        )
    bot.send_message(message.chat.id, txt)

@bot.message_handler(commands=["cancel"])
def cancel(message):
    uid = message.from_user.id
    if uid in user_states:
        del user_states[uid]
        bot.send_message(message.chat.id, "Действие отменено ✅", reply_markup=types.ReplyKeyboardRemove())
    else:
        bot.send_message(message.chat.id, "Нечего отменять.")

@bot.message_handler(commands=["list"])
def list_category(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "Используй: /list <категория>\nПример: /list айти")
        return
    category = args[1].lower()
    if category not in ALLOWED_CATEGORIES:
        bot.send_message(message.chat.id, f"Категория должна быть из списка: {', '.join(ALLOWED_CATEGORIES)}")
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT word, definition FROM slang WHERE category = ?", (category,))
    results = cur.fetchall()
    conn.close()
    if not results:
        bot.send_message(message.chat.id, f"Слова в категории '{category}' пока не добавлены.")
        return
    msg = f"Слова в категории '{category}':\n"
    for word, definition in results:
        msg += f"📌 {word} — {definition}\n"
    bot.send_message(message.chat.id, msg)

# --- Админские команды ---
@bot.message_handler(commands=["pending"])
def list_pending(message):
    uid = message.from_user.id
    if uid not in ADMINS:
        bot.send_message(message.chat.id, "Только админ может просматривать предложения.")
        return
    pending = get_pending()
    if not pending:
        bot.send_message(message.chat.id, "Нет предложенных слов.")
        return
    msg = "Предложенные слова:\n"
    for pid, word, definition, category, user_id in pending:
        msg += f"ID {pid}: {word} — {definition} (категория: {category})\n"
    bot.send_message(message.chat.id, msg)

@bot.message_handler(commands=["approve"])
def approve(message):
    uid = message.from_user.id
    if uid not in ADMINS:
        bot.send_message(message.chat.id, "Только админ может одобрять слова.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "Используй: /approve <id>")
        return
    approve_word(int(args[1]))
    bot.send_message(message.chat.id, f"Слово ID {args[1]} одобрено и добавлено ✅")

@bot.message_handler(commands=["reject"])
def reject(message):
    uid = message.from_user.id
    if uid not in ADMINS:
        bot.send_message(message.chat.id, "Только админ может отклонять слова.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, "Используй: /reject <id>")
        return
    reject_word(int(args[1]))
    bot.send_message(message.chat.id, f"Слово ID {args[1]} отклонено ❌")


    # --- специальные вопросы ---
SPECIAL_QUESTIONS = {
    "какие есть категории": lambda m: bot.send_message(m.chat.id, "Существующие категории: " + ", ".join(ALLOWED_CATEGORIES)),
    "список категорий": lambda m: bot.send_message(m.chat.id, "Существующие категории: " + ", ".join(ALLOWED_CATEGORIES)),
    "какие команды есть": lambda m: send_commands(m),
    "что ты умеешь": lambda m: send_commands(m)
}

def send_commands(message):
    uid = message.from_user.id
    if uid in ADMINS:
        bot.send_message(message.chat.id,
                         "Команды для админа:\n"
                         "/list <категория> — показать все слова в категории\n"
                         "/pending — список предложенных слов\n"
                         "/approve <id> — одобрить предложение\n"
                         "/reject <id> — отклонить предложение\n"
                         "/cancel — отменить текущее действие")
    else:
        bot.send_message(message.chat.id,
                         "Команды для пользователей:\n"
                         "/list <категория> — показать все слова в категории\n"
                         "/cancel — отменить текущее действие")


@bot.message_handler(func=lambda m: True)
def handle_message(message):
    if not message.text:
        return
    uid = message.from_user.id
    text_raw = message.text.strip()
    text = text_raw.lower()

    # --- обработка специальных вопросов ---
    for q, func in SPECIAL_QUESTIONS.items():
        if q in text:
            func(message)
            return


    # --- показать слова по словесному запросу ---
    if "список слов в категории" in text or "покажи слова в категории" in text:
        for cat in ALLOWED_CATEGORIES:
            if cat in text:
                message.text = f"/list {cat}"
                list_category(message)
                return  # <-- return должен быть здесь, внутри функции


    # Игнорировать длинные фразы
    if len(text.split()) > 3:
        bot.send_message(message.chat.id, "Напиши одно слово, чтобы получить определение или предложить его.")
        return

    state = user_states.get(uid)

    # Если ждём подтверждение добавления
    if state and state.get("await_add_confirm"):
        if text in ("да", "д", "yes", "y", "добавить"):
            word = state["word"]
            bot.send_message(message.chat.id, "Напиши краткое определение (или /cancel):", reply_markup=types.ReplyKeyboardRemove())
            user_states[uid] = {"adding_def": True, "word": word}
        else:
            bot.send_message(message.chat.id, "Окей, не добавляем.", reply_markup=types.ReplyKeyboardRemove())
            del user_states[uid]
        return

    # Если ждём определения
    if state and state.get("adding_def"):
        definition = text_raw
        user_states[uid]["definition"] = definition
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        for c in ALLOWED_CATEGORIES:
            markup.add(types.KeyboardButton(c))
        markup.add(types.KeyboardButton("Отмена"))
        bot.send_message(message.chat.id, "Выбери категорию:", reply_markup=markup)
        user_states[uid]["adding_def"] = False
        user_states[uid]["adding_cat"] = True
        return

    # Если ждём категорию
    if state and state.get("adding_cat"):
        if text == "отмена":
            bot.send_message(message.chat.id, "Действие отменено.", reply_markup=types.ReplyKeyboardRemove())
            del user_states[uid]
            return
        if text not in ALLOWED_CATEGORIES:
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
            for c in ALLOWED_CATEGORIES:
                markup.add(types.KeyboardButton(c))
            markup.add(types.KeyboardButton("Отмена"))
            bot.send_message(message.chat.id, "Категория должна быть из списка.", reply_markup=markup)
            return
        word = user_states[uid]["word"]
        definition = user_states[uid]["definition"]
        if uid in ADMINS:
            ok = add_word(word, definition, text)
            if ok:
                bot.send_message(message.chat.id, f"Слово '{word}' добавлено ✅ (категория: {text})", reply_markup=types.ReplyKeyboardRemove())
            else:
                bot.send_message(message.chat.id, f"Слово '{word}' уже есть в этой категории.", reply_markup=types.ReplyKeyboardRemove())
        else:
            add_pending(word, definition, text, uid)
            bot.send_message(message.chat.id, f"Слово '{word}' предложено администратору ✅", reply_markup=types.ReplyKeyboardRemove())
        del user_states[uid]
        return

    # Поиск слова
    found = get_definitions(text)
    if found:
        msg = f"📖 {text}:\n"
        for definition, category in found:
            msg += f"• {definition} (категория: {category})\n"
        bot.send_message(message.chat.id, msg)
    else:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        markup.add(types.KeyboardButton("Да"), types.KeyboardButton("Нет"))
        bot.send_message(message.chat.id,
                         f"Я пока не знаю слова '{text}'. Предложить его администратору? (Да/Нет)",
                         reply_markup=markup)
        user_states[uid] = {"await_add_confirm": True, "word": text}

print("Бот запущен...")
bot.polling(none_stop=True)