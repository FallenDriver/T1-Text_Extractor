"""
Smart Contract Parser API.

Отличия от первой версии прототипа:
- текст из файла достаётся через common/parsers.py (общий модуль, а не
  дублированный код прямо в этом файле)
- сам файл сохраняется через common/storage.py (LocalStorage или
  SupabaseStorage — выбирается переменной окружения STORAGE_BACKEND),
  а не выбрасывается после анализа
- данные пишутся не в самодельную таблицу, а в вашу настоящую схему
  (database/schema.sql): documents + extracted_fields
- работает и с локальным SQLite (для разработки), и с Postgres/Supabase
  (для продакшена) — через один и тот же код, благодаря SQLAlchemy Core

Запуск:
    uvicorn app.main:app --reload
(запускать из корня проекта, там же где лежат папки common/, static/, database/)
"""

import os
import re
import json
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import create_engine, text

from common.parsers import extract_text
from common.storage import LocalStorage, SupabaseStorage

# --------------------------------------------------------------------------
# Конфигурация
# --------------------------------------------------------------------------

load_dotenv()

POLZA_API_KEY = os.getenv("POLZA_API_KEY")
POLZA_API_URL = os.getenv("POLZA_API_URL")

# По умолчанию — локальный SQLite (удобно для разработки без интернета).
# Как только в .env появится DATABASE_URL от Supabase — код автоматически
# переключится на Postgres, менять ничего не нужно.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./database/contracts.db")

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=_connect_args)

# Хранилище файлов: локальный диск по умолчанию, Supabase Storage — если
# явно указано в .env (STORAGE_BACKEND=supabase)
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
if STORAGE_BACKEND == "supabase":
    storage = SupabaseStorage(
        url=os.environ["SUPABASE_URL"],
        key=os.environ["SUPABASE_KEY"],
    )
else:
    storage = LocalStorage(base_dir="storage/uploads")

FIELD_NAMES = ["number", "date", "parties", "amount"]

STATIC_INDEX = Path(__file__).resolve().parent.parent / "static" / "index.html"

app = FastAPI(title="Smart Contract Parser API")


# --------------------------------------------------------------------------
# Вызов LLM для извлечения полей
# --------------------------------------------------------------------------

async def get_attributes_from_ai(text_content: str) -> dict:
    headers = {
        "Authorization": f"Bearer {POLZA_API_KEY}",
        "Content-Type": "application/json",
    }
    prompt = f"""
    Извлеки из текста договора 4 атрибута.
    Верни СТРОГО JSON: {{"number": "номер", "date": "дата", "parties": "стороны", "amount": "сумма"}}.
    Если чего-то нет, пиши "Не найдено". Текст: {text_content[:4000]}
    """
    payload = {
        "model": "openai/gpt-4o-mini",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.1,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            res = await client.post(POLZA_API_URL, headers=headers, json=payload)
            res.raise_for_status()
            ai_text = res.json()["choices"][0]["message"]["content"].strip()

            # Устойчиво достаём JSON-объект из ответа модели, даже если он
            # обёрнут в ```json ... ``` или содержит лишний текст вокруг —
            # просто ищем первую { и последнюю } вместо жёсткой обрезки
            # по количеству символов (как было в первой версии).
            match = re.search(r"\{.*\}", ai_text, re.DOTALL)
            if not match:
                raise ValueError(f"JSON не найден в ответе модели: {ai_text[:200]}")
            return json.loads(match.group(0))
        except Exception as e:
            print(f"[AI Error] {e}")
            return {name: "Ошибка ИИ" for name in FIELD_NAMES}


# --------------------------------------------------------------------------
# Роуты
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def read_index():
    return STATIC_INDEX.read_text(encoding="utf-8")


@app.get("/api/documents")
def get_documents():
    """
    Отдаёт список документов с их полями. Поля лежат построчно в
    extracted_fields, поэтому здесь их "разворачиваем" обратно в колонки
    (number/date/parties/amount) через условную агрегацию — фронтенду
    так намного удобнее, чем присылать вложенный список полей.
    """
    query = text(
        """
        SELECT
            d.id,
            d.filename,
            MAX(CASE WHEN ef.field_name = 'number'  THEN ef.field_value END) AS number,
            MAX(CASE WHEN ef.field_name = 'date'    THEN ef.field_value END) AS date,
            MAX(CASE WHEN ef.field_name = 'parties' THEN ef.field_value END) AS parties,
            MAX(CASE WHEN ef.field_name = 'amount'  THEN ef.field_value END) AS amount
        FROM documents d
        LEFT JOIN extracted_fields ef ON ef.document_id = d.id
        GROUP BY d.id, d.filename, d.uploaded_at
        ORDER BY d.uploaded_at DESC
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query).mappings().all()

    return [
        {
            "id": row["id"],
            "filename": row["filename"],
            "number": row["number"] or "N/A",
            "date": row["date"] or "N/A",
            "parties": row["parties"] or "N/A",
            "amount": row["amount"] or "N/A",
        }
        for row in rows
    ]


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".pdf", ".docx")):
        raise HTTPException(status_code=400, detail="Только PDF или DOCX")

    file_bytes = await file.read()

    # 1. Извлекаем текст (общий парсер, используется и здесь, и в src/)
    raw_text = extract_text(file_bytes, file.filename)
    if not raw_text.strip():
        raise HTTPException(status_code=400, detail="Не удалось извлечь текст из файла")

    # 2. Спрашиваем ИИ
    extracted_data = await get_attributes_from_ai(raw_text)

    # 3. Сохраняем сам файл в хранилище (диск или Supabase — в зависимости от .env)
    document_id = str(uuid.uuid4())
    file_type = "pdf" if file.filename.lower().endswith(".pdf") else "docx"
    file_path = storage.save(document_id, file.filename, file_bytes)

    # 4. Пишем в БД: одна строка в documents + по одной строке в
    #    extracted_fields на каждое извлечённое поле (method='llm' —
    #    пригодится, когда добавите ещё regex/Natasha и захотите сравнить)
    with engine.begin() as conn:
        conn.execute(
            text(
                """INSERT INTO documents (id, filename, file_path, file_type, status)
                   VALUES (:id, :filename, :file_path, :file_type, 'processed')"""
            ),
            {
                "id": document_id,
                "filename": file.filename,
                "file_path": file_path,
                "file_type": file_type,
            },
        )
        for field_name in FIELD_NAMES:
            conn.execute(
                text(
                    """INSERT INTO extracted_fields (id, document_id, field_name, field_value, method)
                       VALUES (:fid, :doc_id, :field_name, :field_value, 'llm')"""
                ),
                {
                    "fid": str(uuid.uuid4()),
                    "doc_id": document_id,
                    "field_name": field_name,
                    "field_value": extracted_data.get(field_name, "Не найдено"),
                },
            )

    return {"status": "success", "data": file.filename}


@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: str):
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT file_path FROM documents WHERE id = :id"), {"id": doc_id}
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Документ не найден")

        conn.execute(text("DELETE FROM extracted_fields WHERE document_id = :id"), {"id": doc_id})
        conn.execute(text("DELETE FROM parties WHERE document_id = :id"), {"id": doc_id})
        conn.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})

    try:
        storage.delete(row[0])
    except Exception as e:
        print(f"[Storage Warning] Не удалось удалить файл {row[0]}: {e}")

    return {"status": "deleted"}
