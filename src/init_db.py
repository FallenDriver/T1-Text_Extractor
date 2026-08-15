"""
Создаёт файл базы данных database/contracts.db на основе database/schema.sql.

Запуск (из корня проекта, там где лежат папки database/ и src/):
    python src/init_db.py

Можно запускать повторно — все таблицы созданы с IF NOT EXISTS,
так что существующие данные не потеряются.
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("database/contracts.db")
SCHEMA_PATH = Path("database/schema.sql")


def main():
    if not SCHEMA_PATH.exists():
        print(f"Не найден файл схемы: {SCHEMA_PATH.resolve()}")
        print("Убедитесь, что вы запускаете скрипт из корня проекта (папка T1-2).")
        return

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema_sql)
        conn.commit()
        print(f"База данных создана: {DB_PATH.resolve()}")

        # сразу покажем, какие таблицы получились - удобно для проверки
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        print("Таблицы в базе:", [t[0] for t in tables])
    finally:
        conn.close()


if __name__ == "__main__":
    main()
