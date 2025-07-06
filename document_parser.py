# document_parser.py

import fitz  # PyMuPDF
import docx
import pandas as pd
import io

# НОВАЯ СИГНАТУРА ФУНКЦИИ!
def get_text_from_file(file_stream: io.BytesIO, filename: str) -> str:
    """Извлекает текст из потока байтов файла (PDF, DOCX, XLSX)."""
    file_extension = filename.split('.')[-1].lower()
    
    if file_extension == 'pdf':
        try:
            # Открываем PDF из потока байтов
            pdf_document = fitz.open(stream=file_stream.read(), filetype="pdf")
            text = ""
            for page_num in range(len(pdf_document)):
                page = pdf_document.load_page(page_num)
                text += page.get_text()
            return text
        except Exception as e:
            print(f"Ошибка чтения PDF: {e}")
            return f"Ошибка при обработке PDF-файла: {filename}"

    elif file_extension == 'docx':
        try:
            # docx.Document может работать напрямую с потоком
            doc = docx.Document(file_stream)
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Ошибка чтения DOCX: {e}")
            return f"Ошибка при обработке DOCX-файла: {filename}"

    elif file_extension in ['xlsx', 'xls']:
        try:
            # pandas также может работать с потоком
            df = pd.read_excel(file_stream, sheet_name=None)
            full_text = ""
            for sheet_name, sheet_df in df.items():
                full_text += f"--- Лист: {sheet_name} ---\n"
                full_text += sheet_df.to_string() + "\n\n"
            return full_text
        except Exception as e:
            print(f"Ошибка чтения XLSX: {e}")
            return f"Ошибка при обработке Excel-файла: {filename}"

    else:
        return f"Формат файла .{file_extension} не поддерживается."