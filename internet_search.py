# internet_search.py

import os
from googleapiclient.discovery import build

def google_search(query: str, num_results=10) -> list:
    """Выполняет поиск в Google и возвращает список результатов."""
    try:
        api_key = os.getenv("SEARCH_API_KEY")
        search_engine_id = os.getenv("SEARCH_ENGINE_ID")
        
        service = build("customsearch", "v1", developerKey=api_key)
        
        res = service.cse().list(
            q=query,
            cx=search_engine_id,
            num=num_results
        ).execute()
        
        return res.get('items', [])
    except Exception as e:
        print(f"Ошибка при поиске в Google: {e}")
        return []