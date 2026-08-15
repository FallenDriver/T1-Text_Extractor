"""
Модуль хранилища файлов.

Идея: весь остальной код (FastAPI-эндпоинты, скрипты) работает
не с диском напрямую, а с этим интерфейсом. Поэтому если позже
понадобится переехать на S3/MinIO — меняется только этот файл,
а не весь проект.

Использование:
    from storage import LocalStorage

    storage = LocalStorage(base_dir="storage/uploads")

    document_id = str(uuid.uuid4())
    file_path = storage.save(document_id, "original.docx", file_bytes)
    # file_path -> "storage/uploads/<document_id>/original.docx"
    # именно эту строку и кладём в documents.file_path в базе данных

    data = storage.load(file_path)   # прочитать файл обратно
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class BaseStorage(ABC):
    """Общий интерфейс хранилища — и локальный диск, и S3 будут его реализовывать."""

    @abstractmethod
    def save(self, document_id: str, filename: str, data: bytes) -> str:
        """Сохраняет файл, возвращает путь/ключ, который нужно записать в БД."""
        raise NotImplementedError

    @abstractmethod
    def load(self, path: str) -> bytes:
        """Читает файл по пути/ключу, сохранённому в БД."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, path: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def exists(self, path: str) -> bool:
        raise NotImplementedError


class LocalStorage(BaseStorage):
    """Хранение файлов на локальном диске — то, что нужно сейчас для учебного проекта."""

    def __init__(self, base_dir: str = "storage/uploads"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _full_path(self, path: str) -> Path:
        # path хранится в БД как относительный путь от base_dir,
        # чтобы можно было безопасно переносить проект между машинами
        return self.base_dir / path

    def save(self, document_id: str, filename: str, data: bytes) -> str:
        doc_dir = self.base_dir / document_id
        doc_dir.mkdir(parents=True, exist_ok=True)
        target = doc_dir / filename
        target.write_bytes(data)
        # возвращаем ОТНОСИТЕЛЬНЫЙ путь (без base_dir) — именно его пишем в documents.file_path
        return str(Path(document_id) / filename)

    def load(self, path: str) -> bytes:
        full = self._full_path(path)
        if not full.exists():
            raise FileNotFoundError(f"Файл не найден: {full}")
        return full.read_bytes()

    def delete(self, path: str) -> None:
        full = self._full_path(path)
        if full.exists():
            shutil.rmtree(full.parent, ignore_errors=True)

    def exists(self, path: str) -> bool:
        return self._full_path(path).exists()


# --------------------------------------------------------------------------
# Облачное хранилище — Supabase Storage (S3-совместимое, бесплатный тариф).
# Реализует тот же интерфейс BaseStorage, поэтому весь остальной код
# (эндпоинты, скрипты populate_db.py и т.д.) не нужно трогать вообще —
# просто в месте создания объекта хранилища меняете LocalStorage(...)
# на SupabaseStorage(...), и всё продолжает работать.
# --------------------------------------------------------------------------

class SupabaseStorage(BaseStorage):
    """
    Требует пакет: pip install supabase python-dotenv

    Использование:
        from dotenv import load_dotenv
        import os
        load_dotenv()

        storage = SupabaseStorage(
            url=os.environ["SUPABASE_URL"],
            key=os.environ["SUPABASE_KEY"],
            bucket="contracts",
        )
    Бакет "contracts" нужно один раз создать в дашборде Supabase:
    Storage -> New bucket -> назвать "contracts" -> Public (для простоты
    на этапе разработки; в проде лучше сделать приватным и раздавать
    временные ссылки через create_signed_url).
    """

    def __init__(self, url: str, key: str, bucket: str = "contracts"):
        from supabase import create_client  # локальный импорт, чтобы
        # библиотека не была обязательной зависимостью для тех, кто
        # использует только LocalStorage
        self.client = create_client(url, key)
        self.bucket = bucket

    def save(self, document_id: str, filename: str, data: bytes) -> str:
        path = f"{document_id}/{filename}"
        self.client.storage.from_(self.bucket).upload(
            path, data, file_options={"upsert": "true"}
        )
        return path  # именно эту строку кладём в documents.file_path

    def load(self, path: str) -> bytes:
        return self.client.storage.from_(self.bucket).download(path)

    def delete(self, path: str) -> None:
        self.client.storage.from_(self.bucket).remove([path])

    def exists(self, path: str) -> bool:
        folder = path.rsplit("/", 1)[0]
        filename = path.rsplit("/", 1)[1]
        files = self.client.storage.from_(self.bucket).list(folder)
        return any(f["name"] == filename for f in files)


if __name__ == "__main__":
    # быстрая самопроверка модуля
    import uuid

    storage = LocalStorage(base_dir="storage/uploads")
    doc_id = str(uuid.uuid4())

    saved_path = storage.save(doc_id, "original.docx", b"test content")
    print("Сохранено по пути (кладём в БД):", saved_path)

    assert storage.exists(saved_path)
    assert storage.load(saved_path) == b"test content"
    print("Самопроверка пройдена: файл сохранён и корректно прочитан обратно.")

    storage.delete(saved_path)
    assert not storage.exists(saved_path)
    print("Удаление работает корректно.")
