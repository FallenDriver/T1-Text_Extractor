import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

# Импортируем наши модули базы данных и роутеры
from database import engine, Base
import models
from routers import users, documents

# Создаем все таблицы в БД по нашей схеме при запуске сервера.
Base.metadata.create_all(bind=engine)

# Инициализируем приложение FastAPI
app = FastAPI(
    title="Smart Contract Parser API",
    description="Модульный MVP парсера договоров на базе NLP/LLM и фоновых задач",
    version="3.0"
)

# Подключаем наши "микросервисы" (роутеры)
app.include_router(users.router, prefix="/api")
app.include_router(documents.router, prefix="/api")

# Отдаем фронтенд
@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
def read_index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Файл index.html не найден</h1><p>Пожалуйста, создайте его в корне проекта.</p>"

if __name__ == "__main__":
    # Запуск через python main.py
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)