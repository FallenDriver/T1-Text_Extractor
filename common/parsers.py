import io
from pypdf import PdfReader
import docx


def extract_text(file_bytes: bytes, filename: str) -> str:
    text = ""
    file_stream = io.BytesIO(file_bytes)

    lower_filename = filename.lower()

    try:
        if lower_filename.endswith('.pdf'):
            reader = PdfReader(file_stream)
            pages_text = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages_text)
            
        elif lower_filename.endswith('.docx'):
            doc = docx.Document(file_stream)
            paragraphs_text = [para.text for para in doc.paragraphs if para.text.strip()]
            text = "\n".join(paragraphs_text)
            
        else:
            raise ValueError(f"Неподдерживаемый формат файла: {filename}")
            
    except Exception as e:
        print(f"[Parser Error] Не удалось извлечь текст из {filename}: {e}")
        return ""
        
    return text.strip()