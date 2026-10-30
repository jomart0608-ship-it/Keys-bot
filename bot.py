import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

Настройка логирования
logging.basicConfig(level=logging.INFO)

API_TOKEN = "8634864746:AAEVjfEBz38PNIyXp1L9DeYV5jbaG0IHLlc"

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

---------------------------------------------------------
1. Справочники объектов (Сайты с типами ключей)
---------------------------------------------------------

OUTDOOR_SITES = {
# OUTDOOR объекты (если появятся)
}

ITO_SITES = {
"81030": {"name": "VODITEL", "category": "Городской", "key_type": "ITO"},
"81105": {"name": "PODSTEPNOE", "category": "Регион", "key_type": "ITO"},
"82005": {"name": "KARACH7KM", "category": "Регион", "key_type": "ITO"},
"82008": {"name": "KOLOVERTNO", "category": "Регион", "key_type": "ITO"},
"82010": {"name": "URALYAIK", "category": "Регион", "key_type": "ITO"},
"82034": {"name": "PRS14AMANG", "category": "Регион", "key_type": "ITO"},
"82092": {"name": "URCHAGAN", "category": "Регион", "key_type": "ITO"},
"82019": {"name": "POGODAEVO", "category": "Регион", "key_type": "ITO"},
}

GENERAL_SITES = {
"82037": {"name": "ALGABASKTW", "category": "Регион", "key_type": "ОБЩИЙ"},
"82095": {"name": "FEDOROVKA", "category": "Регион", "key_type": "ОБЩИЙ"},
"82096": {"name": "AKZHAIYK", "category": "Регион", "key_type": "ОБЩИЙ"},
"82129": {"name": "DOLINNOE", "category": "Регион", "key_type": "ОБЩИЙ"},
}

GUARD_SITES = {
"81005": {"name": "URINTEK", "category": "Городской", "key_type": "ОХРАНА"},
"81009": {"name": "URTALAP", "category": "Городской", "key_type": "ОХРАНА"},
"81044": {"name": "ZENITDK", "category": "Городской", "key_type": "ОХРАНА"},
"82011": {"name": "CHAPAEVZKO", "category": "Регион", "key_type": "ОХРАНА"},
"81046": {"name": "SDUSOR", "category": "Городской", "key_type": "ОХРАНА"},
"82133": {"name": "DZHANGKZT", "category": "Регион", "key_type": "ОХРАНА"},
}

---------------------------------------------------------
2. Инициализация и работа с БД SQLite
---------------------------------------------------------

def init_db():
conn = sqlite3.connect("station_keys.db")
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS key_logs (
id INTEGER PRIMARY KEY AUTOINCREMENT,
site_id TEXT,
site_type TEXT,
site_category TEXT,
key_type TEXT,
action TEXT,
person_from TEXT,
person_to TEXT,
telegram_user TEXT,
timestamp DATETIME DEFAULT (datetime('now', '+5 hours'))
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS key_stand (
site_id TEXT PRIMARY KEY,
site_type TEXT,
site_category TEXT,
key_type TEXT,
status TEXT,
current_holder TEXT,
taken_at DATETIME
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS sites_to_check (
id INTEGER PRIMARY KEY AUTOINCREMENT,
raw_input TEXT,
telegram_user TEXT,
timestamp DATETIME DEFAULT (datetime('now', '+5 hours'))
)
''')

for site_id, info in GUARD_SITES.items():
cursor.execute(
"""
INSERT OR IGNORE INTO key_stand (site_id, site_type, site_category, key_type, status, current_holder)
VALUES (?, ?, ?, ?, ?, ?)
""",
(site_id, info["name"], info["category"], info["key_type"], "у охраны", "Охрана здания")
)

conn.commit()
conn.close()

---------------------------------------------------------
3. Вспомогательные функции
---------------------------------------------------------

def resolve_site_info(raw_input: str):
clean_input = raw_input.strip().upper()

all_dicts = [OUTDOOR_SITES, ITO_SITES, GENERAL_SITES, GUARD_SITES]
for site_dict in all_dicts:
for site_id, info in site_dict.items():
if site_id in clean_input or info["name"] in clean_input:
return site_id, info["name"], info["category"], info["key_type"], True

return clean_input, "Неизвестен", "Неизвестна", "НЕИЗВЕСТНО", False

def log_unresolved_site(raw_input: str, telegram_user: str):
conn = sqlite3.connect("station_keys.db")
cursor = conn.cursor()
cursor.execute(
"INSERT INTO sites_to_check (raw_input, telegram_user) VALUES (?, ?)",
(raw_input, telegram_user)
)
conn.commit()
conn.close()

def process_key_action(raw_site_name: str, action: str, person_from: str, person_to: str, telegram_user: str):
site_id, site_type, site_category, key_type, found = resolve_site_info(raw_site_name)

if not found:
log_unresolved_site(raw_site_name, telegram_user)
return (
f"❌ Сайт {raw_site_name} не найден / нет информации.\n\n"
f"⚠️ Прошу скорректировать запрос (проверьте правильность номера или названия объекта)."
)

conn = sqlite3.connect("station_keys.db")
cursor = conn.cursor()

target = person_to.lower().strip()

if key_type == "ОХРАНА" or target in ["у охраны", "охрана"]:
new_status = "у охраны"
holder_name = "Охрана здания"
taken_at_val = None
elif target in ["на сайте", "на бс", "на объекте"]:
new_status = "на сайте"
holder_name = "На сайте"
taken_at_val = None
else:
new_status = "у сотрудника"
holder_name = person_to
cursor.execute("SELECT datetime('now', '+5 hours')")
taken_at_val = cursor.fetchone()[0]

cursor.execute(
"""
INSERT INTO key_logs (site_id, site_type, site_category, key_type, action, person_from, person_to, telegram_user)
VALUES (?, ?, ?, ?, ?, ?, ?, ?)
""",
(site_id, site_type, site_category, key_type, action, person_from, person_to, telegram_user)
)

cursor.execute(
"""
INSERT INTO key_stand (site_id, site_type, site_category, key_type, status, current_holder, taken_at)
VALUES (?, ?, ?, ?, ?, ?, ?)
ON CONFLICT(site_id) DO UPDATE SET
status = excluded.status,
current_holder = excluded.current_holder,
site_type = excluded.site_type,
site_category = excluded.site_category,
key_type = excluded.key_type,
taken_at = excluded.taken_at
""",
(site_id, site_type, site_category, key_type, new_status, holder_name, taken_at_val)
)

conn.commit()
conn.close()

return (
f"✅ Операция зарегистрирована!\n"
f"• БС: {site_id} ({site_type}) [{key_type}]\n"
f"• Статус: {new_status} ➔ {holder_name}"
)

---------------------------------------------------------
4. Обработчики команд Telegram
---------------------------------------------------------

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
await message.answer("👋 Бот учета ключей Kcell готов к работе!")

@dp.message(Command("who"))
async def cmd_who(message: types.Message):
conn = sqlite3.connect("station_keys.db")
cursor = conn.cursor()
cursor.execute("SELECT site_id, site_type, key_type, current_holder, taken_at FROM key_stand WHERE status = 'у сотрудника'")
rows = cursor.fetchall()
conn.close()

if not rows:
await message.answer("🎉 На руках у сотрудников нет ключей!")
return

report = "🔴 Ключи на руках у инженеров:\n\n"
for row in rows:
site_id, site_type, key_type, holder, taken_at = row
time_str = f" (взят: {taken_at})" if taken_at else ""
report += f"• БС {site_id} ({site_type}) [{key_type}] ➔ {holder}{time_str}\n"

await message.answer(report, parse_mode="Markdown")

@dp.message(Command("check_errors", "unknown"))
async def cmd_check_errors(message: types.Message):
conn = sqlite3.connect("station_keys.db")
cursor = conn.cursor()
cursor.execute("SELECT raw_input, telegram_user, timestamp FROM sites_to_check ORDER BY id DESC LIMIT 10")
rows = cursor.fetchall()
conn.close()

if not rows:
await message.answer("🎉 Нет неопознанных запросов! Все введенные сайты распознаны.")
return

report = "⚠️ Список сайтов, требующих исправления (не найдены):\n\n"
for row in rows:
raw_input, user, ts = row
report += f"• Ввод: {raw_input} (пользователь: @{user or 'неизвестен'}, время: {ts})\n"

report += "\n💡 Проверьте корректность запросов и при необходимости добавьте объекты в справочники."
await message.answer(report, parse_mode="Markdown")

---------------------------------------------------------
5. Запуск бота
---------------------------------------------------------

async def main():
init_db()
print("БД инициализирована. Запуск бота...")
await dp.start_polling(bot)

if name == "main":
asyncio.run(main())