"""
Утилита для ручной проверки парсера на одном файле.

Запуск (из корня проекта):
    python src/parse_one.py dataset/docx/contract_0001.docx
"""

import sys
import os
import time
from pathlib import Path

# добавляем корень проекта в sys.path, чтобы работал импорт из common/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.parsers import extract_text


def main():
    if len(sys.argv) < 2:
        print("Использование: python src/parse_one.py <путь_к_файлу>")
        print("Пример: python src/parse_one.py dataset/docx/contract_0001.docx")
        sys.exit(1)

    filepath = sys.argv[1]

    if not os.path.exists(filepath):
        print(f"Файл не найден: {filepath}")
        sys.exit(1)

    filename = os.path.basename(filepath)
    print(f"Обработка {filename}")

    with open(filepath, "rb") as f:
        file_bytes = f.read()

    start = time.perf_counter()
    text = extract_text(file_bytes, filename)
    elapsed = time.perf_counter() - start

    if not text.strip():
        print("Текст не извлечён (пустой результат)")
        sys.exit(1)

    output_path = os.path.splitext(filepath)[0] + "_parsed.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Извлечено {len(text):,} символов за {elapsed:.2f} сек")
    print(f"Сохранено: {output_path}")


if __name__ == "__main__":
    main()
