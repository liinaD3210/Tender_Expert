# llm_handler.py
import google.generativeai as genai
import json
import os
from dotenv import load_dotenv

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

# Настраиваем модель
generation_config = {
  "temperature": 0.1, # Низкая температура для точности
  "top_p": 1,
  "top_k": 1,
  "max_output_tokens": 8192,
}

model = genai.GenerativeModel(model_name="gemini-1.5-flash-latest",
                              generation_config=generation_config)

def extract_data_from_text(text: str, supplier_name: str) -> list:
    """Извлекает табличные данные из текста с помощью LLM."""
    
    prompt = f"""
    ТЫ — AI-аналитик отдела закупок. Твоя задача — извлечь из текста коммерческого предложения все товарные позиции.
    
    ИНСТРУКЦИИ:
    1. Внимательно проанализируй текст. Текст может быть "грязным", полученным после OCR скана.
    2. Найди все строки, содержащие наименование товара, количество, единицу измерения и цену. НЕ ПРИДУМЫВАЙ данные, которых нет в тексте.
    3. Если какой-то параметр отсутствует (например, артикул, количество или цена), оставь поле пустым (null) или пропусти его.
    4. Цены и количество должны быть только числами. Убери из них "руб.", "шт." и т.д.
    5. Верни результат ТОЛЬКО в формате JSON-массива. Никаких лишних слов, объяснений или ```json```.
    
    Пример JSON-объекта для одной позиции:
    {{
      "name": "Наименование товара",
      "sku": "Артикул или код (если есть)",
      "quantity": 10,
      "unit": "шт.",
      "price_per_unit": 1500.50,
      "total_price": 15005.00
    }}

    ТЕКСТ ДЛЯ АНАЛИЗА:
    ---
    {text}
    ---
    """
    
    try:
        response = model.generate_content(prompt)
        # Попытка исправить "грязный" JSON от модели
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        extracted_data = json.loads(cleaned_response)
        # Добавляем имя поставщика к каждой позиции
        for item in extracted_data:
            item['supplier'] = supplier_name
        return extracted_data
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"Ошибка декодирования JSON или ответа от API: {e}")
        print(f"Ответ модели, который не удалось распарсить: {response.text}")
        return []


def normalize_and_group_items(items: list) -> list:
    """Группирует одинаковые товары от разных поставщиков с помощью LLM."""
    
    prompt = f"""
    ТЫ — AI-эксперт по нормализации данных. Тебе предоставлен JSON-массив с товарами от РАЗНЫХ поставщиков.
    
    ЗАДАЧА:
    1. Сгруппируй семантически одинаковые товары. "Подшипник 6205-2RS" и "Подшипник шариковый арт. 6205" - это ОДИН и тот же товар.
    2. Для каждой группы товаров создай единое "каноничное" наименование.
    3. Верни результат ТОЛЬКО в виде JSON-массива, где каждый элемент — это уникальный товар, содержащий список предложений от поставщиков.
    
    СТРУКТУРА ВЫХОДНОГО JSON:
    [
      {{
        "canonical_name": "Единое название товара 1",
        "offers": [
          {{ "supplier": "Поставщик А", "price_per_unit": 100.00 }},
          {{ "supplier": "Поставщик Б", "price_per_unit": 105.50 }}
        ]
      }},
      {{
        "canonical_name": "Единое название товара 2",
        "offers": [
          {{ "supplier": "Поставщик А", "price_per_unit": 220.00 }}
        ]
      }}
    ]

    ВХОДНЫЕ ДАННЫЕ (JSON):
    ---
    {json.dumps(items, ensure_ascii=False, indent=2)}
    ---
    """
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        grouped_data = json.loads(cleaned_response)
        return grouped_data
    except (json.JSONDecodeError, AttributeError, ValueError) as e:
        print(f"Ошибка декодирования JSON на этапе нормализации: {e}")
        print(f"Ответ модели, который не удалось распарсить: {response.text}")
        return []
    
def generate_tender_insight(df_as_json: str, totals: dict) -> str:
    """Генерирует аналитическую сводку и рекомендации по закупке."""
    
    prompt = f"""
    ТЫ — AI-эксперт по закупкам. Тебе предоставлены результаты сравнения коммерческих предложений в формате JSON.
    
    ТВОЯ ЗАДАЧА:
    Написать короткую (2-3 предложения), но емкую аналитическую сводку для менеджера по закупкам.
    
    ОБЯЗАТЕЛЬНО УКАЖИ:
    1. У какого поставщика самая низкая ОБЩАЯ сумма по всем позициям. Назови поставщика и сумму.
    2. Проанализируй данные по строкам. Есть ли возможность получить ДОПОЛНИТЕЛЬНУЮ экономию, если разделить закупку между несколькими поставщиками?
    3. Если да, то приведи пример: "Например, закупив [Название товара 1] у [Поставщик А], а [Название товара 2] у [Поставщик Б], можно оптимизировать расходы."
    4. Сделай вывод в деловом, но понятном стиле. Обращайся к пользователю уважительно.

    ВХОДНЫЕ ДАННЫЕ:
    
    1. Итоговая сравнительная таблица (в формате JSON):
    {df_as_json}

    2. Общие суммы по каждому поставщику:
    {json.dumps(totals, ensure_ascii=False, indent=2)}

    ТВОЙ АНАЛИТИЧЕСКИЙ ВЫВОД:
    """
    
    try:
        # Используем ту же модель, но с большей "креативностью"
        insight_model = genai.GenerativeModel(
            model_name="gemini-1.5-flash-latest",
            generation_config={"temperature": 0.5} # Температуру можно чуть поднять для генерации текста
        )
        response = insight_model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Ошибка при генерации инсайта: {e}")
        return "Не удалось сгенерировать аналитический вывод."
    
def generate_search_query(item_name: str) -> str:
    """Преобразует название товара в эффективный поисковый запрос."""
    
    prompt = f"""
    ТЫ — AI-ассистент в отделе закупок.
    Твоя задача — создать идеальный поисковый запрос для Google, чтобы найти лучшую цену на товар.
    Добавь ключевые слова вроде "купить", "цена", "стоимость".
    
    Название товара: "{item_name}"
    
    Сгенерируй только строку запроса. Без лишних слов.
    """
    try:
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except Exception as e:
        print(f"Ошибка при генерации поискового запроса: {e}")
        return item_name # В случае ошибки ищем как есть

def analyze_search_results(search_results: list, item_name: str) -> list:
    """Анализирует результаты поиска Google и извлекает предложения."""
    
    # Формируем контекст для модели из результатов поиска
    context = ""
    for i, result in enumerate(search_results):
        context += f"--- Результат поиска №{i+1} ---\n"
        context += f"Заголовок: {result.get('title', '')}\n"
        context += f"Ссылка: {result.get('link', '')}\n"
        context += f"Фрагмент текста: {result.get('snippet', '')}\n\n"

    prompt = f"""
    ТЫ — AI-аналитик, изучающий поисковую выдачу.
    Твоя задача — найти коммерческие предложения на товар "{item_name}" в предоставленных фрагментах текста из поиска Google.

    ИНСТРУКЦИИ:
    1. Проанализируй каждый "Результат поиска".
    2. Если во фрагменте текста есть упоминание цены и название компании/магазина, извлеки эти данные.
    3. Цена должна быть числом.
    4. Если цена не найдена, пропусти этот результат.
    5. Верни результат ТОЛЬКО в формате JSON-массива. Каждый элемент — одно найденное предложение.
    
    Пример формата JSON:
    [
      {{
        "supplier_name": "ООО ПромСнаб",
        "price": 15200.50,
        "link": "https://somesite.com/product",
        "snippet": "Краткое описание предложения с ценой..."
      }}
    ]

    ТЕКСТ ДЛЯ АНАЛИЗА (РЕЗУЛЬТАТЫ ПОИСКА):
    ---
    {context}
    ---
    """
    
    try:
        response = model.generate_content(prompt)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        return json.loads(cleaned_response)
    except Exception as e:
        print(f"Ошибка при анализе результатов поиска: {e}")
        print(f"Ответ модели: {response.text}")
        return []