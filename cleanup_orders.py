"""Автоочистка таблицы «Заказы» в NocoDB: удаляет записи старше ORDERS_KEEP_DAYS (по умолчанию 14) дней.
Нужны переменные окружения: NOCODB_TOKEN, ORDERS_TABLE_ID (id таблицы «Заказы»). Без ORDERS_TABLE_ID — тихо выходит."""
import os, sys, datetime
import requests

BASE = os.environ.get("NOCODB_URL", "https://app.nocodb.com").rstrip("/")
TOKEN = os.environ.get("NOCODB_TOKEN", "")
TABLE = os.environ.get("ORDERS_TABLE_ID", "").strip()
KEEP_DAYS = int(os.environ.get("ORDERS_KEEP_DAYS", "14"))


def parse_dt(v):
    if not v:
        return None
    s = str(v).strip().replace("Z", "+00:00")
    try:
        d = datetime.datetime.fromisoformat(s)
    except ValueError:
        try:
            d = datetime.datetime.fromisoformat(s[:19])
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=datetime.timezone.utc)
    return d


def main():
    if not TABLE:
        print("ORDERS_TABLE_ID не задан — очистка пропущена")
        return 0
    if not TOKEN:
        print("Не задан NOCODB_TOKEN", file=sys.stderr)
        return 1
    h = {"xc-token": TOKEN}
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=KEEP_DAYS)
    old, offset, total = [], 0, 0
    while True:
        r = requests.get(f"{BASE}/api/v2/tables/{TABLE}/records", headers=h, timeout=60,
                         params={"limit": 1000, "offset": offset, "fields": "Id,CreatedAt"})
        r.raise_for_status()
        data = r.json()
        rows = data.get("list", [])
        for row in rows:
            total += 1
            d = parse_dt(row.get("CreatedAt"))
            if d is not None and d < cutoff:     # нет даты — не трогаем
                old.append({"Id": row["Id"]})
        if data.get("pageInfo", {}).get("isLastPage", True) or not rows:
            break
        offset += len(rows)
    print(f"Записей: {total}, старше {KEEP_DAYS} дн.: {len(old)}")
    for i in range(0, len(old), 100):
        r = requests.delete(f"{BASE}/api/v2/tables/{TABLE}/records", headers=h, json=old[i:i + 100], timeout=60)
        r.raise_for_status()
    print("Удалено:", len(old))
    return 0


if __name__ == "__main__":
    sys.exit(main())
