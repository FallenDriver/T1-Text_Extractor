# ContractAI — Sprint 1

Автоматизация извлечения полей (номер, дата, сумма, стороны) из договоров.

## Порядок запуска

### 1. Генерация датасета
```bash
python src/generate_contracts.py --count 30 --out ./dataset
```
Создаёт 30 DOCX-договоров и labels.json с эталонной разметкой.

### 2. Конвертация в PDF (Windows + Word)
```powershell
powershell -File src/convert_to_pdf.ps1
```
Создаёт PDF-версии первых 10 договоров.

### 3. Создание базы данных и загрузка разметки
```bash
python src/init_db.py
python src/populate_db.py
```
Создаёт SQLite-базу и заполняет её данными из labels.json.

### 4. Запуск веб-сервиса
```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Откройте http://127.0.0.1:8000 — форма загрузки договора и реестр обработанных документов.

Перед запуском создайте `.env` в корне проекта (см. `.env.example`):
```
POLZA_API_KEY=ваш_ключ
POLZA_API_URL=адрес_эндпоинта
DATABASE_URL=sqlite:///./database/contracts.db
STORAGE_BACKEND=local
```
Чтобы переключиться на Supabase — смените `DATABASE_URL` на строку подключения из Supabase (Connect → Connection string) и `STORAGE_BACKEND=supabase`, добавив `SUPABASE_URL` и `SUPABASE_KEY`.

## Структура проекта

| Папка | Содержимое |
|-------|------------|
| app/ | main.py — FastAPI-бэкенд (загрузка, извлечение полей через ИИ, реестр) |
| common/ | parsers.py (извлечение текста из PDF/DOCX) и storage.py (хранилище файлов: локально или Supabase) — общий код для app/ и src/ |
| static/ | index.html — фронтенд реестра |
| dataset/docx/ | 30 синтетических договоров |
| dataset/pdf/ | 10 PDF-версий |
| dataset/annotations/ | labels.json + manual_labels.csv |
| database/ | schema.sql + contracts.db |
| docs/ | architecture.md + api_contract.md |
| src/ | generate_contracts.py, populate_db.py, init_db.py, convert_to_pdf.ps1, parse_one.py |

## Зависимости
```bash
pip install -r requirements.txt
```