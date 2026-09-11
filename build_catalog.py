import os
import json
import time
import requests

NOCODB_URL = "https://app.nocodb.com"
TABLE_ID = "mzyn24rg2qoo8xs" 
TOKEN = os.environ.get("NOCODB_TOKEN", "")

# Паузы между запросами для обхода лимитов бесплатного тарифа
PAGE_DELAY = 0.6
MAX_RETRIES = 6

def request_with_retry(url, **kwargs):
    """GET-запрос с повторными попытками при 429 (Too Many Requests)."""
    delay = 2
    for attempt in range(1, MAX_RETRIES + 1):
        resp = requests.get(url, **kwargs)
        if resp.status_code == 429:
            retry_after = resp.headers.get("Retry-After")
            wait = float(retry_after) if retry_after else delay
            print(f"  429 от сервера, жду {wait:.0f}с (попытка {attempt}/{MAX_RETRIES})")
            time.sleep(wait)
            delay = min(delay * 2, 30)
            continue
        resp.raise_for_status()
        return resp
    resp.raise_for_status()
    return resp

def fetch_all_records():
    """Постраничная загрузка всех товаров из таблицы."""
    all_records = []
    offset = 0
    print("Начинаем выгрузку данных из NocoDB...")
    
    while True:
        resp = request_with_retry(
            f"{NOCODB_URL}/api/v2/tables/{TABLE_ID}/records",
            headers={"xc-token": TOKEN},
            params={"limit": 200, "offset": offset},
            timeout=30,
        )
        data = resp.json()
        page = data.get("list", [])
        all_records.extend(page)
        
        print(f"  Скачано {len(all_records)} записей...")
        
        # Прерываем цикл, если список пуст или это последняя страница
        if not page or data.get("pageInfo", {}).get("isLastPage"):
            break
            
        offset += len(page)
        time.sleep(PAGE_DELAY)
        
    return all_records

def main():
    if not TOKEN:
        print("Ошибка: Не задан NOCODB_TOKEN в переменных окружения!")
        return

    records = fetch_all_records()
    
    # Отфильтровываем пустые строки (на случай случайных пробелов в базе)
    valid_records = [r for r in records if str(r.get("Name", "")).strip()]
    
    # Сохраняем результат
    output_file = "catalog.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(valid_records, f, ensure_ascii=False, separators=(',', ':'))
        
    size_kb = os.path.getsize(output_file) / 1024
    print(f"Успешно сохранено {len(valid_records)} записей в {output_file} ({size_kb:.0f} КБ)")

if __name__ == "__main__":
    main()
