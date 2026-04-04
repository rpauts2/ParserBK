# Инструкция по запуску парсера Лиги Ставок

## Проблема защиты QRATOR
Сайт ligastavok.ru защищён системой QRATOR, которая блокирует автоматические запросы. 
Для обхода защиты требуется выполнение JavaScript челленджа, что возможно только через реальный браузер.

## Способ 1: Установка на свою машину (РЕКОМЕНДУЕМЫЙ)

### Шаг 1: Установка зависимостей
```bash
pip install playwright aiohttp playwright_stealth
playwright install chromium
```

### Шаг 2: Запуск парсера
```bash
cd betting_parsers
python ligastavok_parser.py
```

Или с использованием Playwright для обхода защиты:
```python
import asyncio
from ligastavok_parser import LigaStavokParser

async def main():
    parser = LigaStavokParser()
    events = await parser.run(use_playwright=True)  # True для использования браузера
    print(f"Найдено событий: {len(events)}")

asyncio.run(main())
```

---

## Способ 2: Использование готовых кук (если нет возможности установить браузер)

### Шаг 1: Экспорт кук из браузера

#### Для Chrome/Chromium:
1. Установите расширение [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
2. Откройте https://www.ligastavok.ru
3. Дождитесь полной загрузки страницы (пройдите проверку если есть)
4. Кликните на иконку расширения → Export → JSON
5. Сохраните файл как `ligastavok_cookies.json`

#### Для Firefox:
1. Установите расширение [Cookie Quick Manager](https://addons.mozilla.org/en-US/firefox/addon/cookie-quick-manager/)
2. Откройте https://www.ligastavok.ru
3. Откройте расширение → Export → JSON
4. Сохраните файл как `ligastavok_cookies.json`

### Шаг 2: Запуск парсера с куками
```python
import asyncio
from ligastavok_parser import LigaStavokParser

async def main():
    # Передаём путь к файлу с куками
    parser = LigaStavokParser(cookies_file='ligastavok_cookies.json')
    events = await parser.run(use_playwright=False)
    print(f"Найдено событий: {len(events)}")
    
    # Пример вывода
    for event in events[:3]:
        print(f"\n{event['match']}")
        print(f"  1={event['odds']['main']['1']}, X={event['odds']['main']['X']}, 2={event['odds']['main']['2']}")

asyncio.run(main())
```

---

## Способ 3: Прямой вызов API (для продвинутых)

Если у вас есть действующие куки, можно делать прямые запросы к API:

```python
import aiohttp
import json
import uuid
import time

async def get_events():
    cookies = [...]  # ваши куки
    
    headers = {
        "Content-Type": "application/json",
        "x-application-name": "mobile",
        "x-req-id": str(uuid.uuid4()),
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36"
    }
    
    cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in cookies])
    headers["Cookie"] = cookies_str
    
    payload = {
        "gameId": [],
        "limit": 100,
        "skip": 0,
        "topEvents": False,
        "ts": int(time.time() * 1000),
        "view": "priority",
        "widgetVideo": False,
        "proposedTypes": ["MAINOFFER"]
    }
    
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.post(
            "https://lds-api-sites.ligastavok.ru/rest/events/v8/eventsList",
            json=payload
        ) as response:
            data = await response.json()
            return data["result"]["data"]

# Использование
events = asyncio.run(get_events())
print(f"Найдено событий: {len(events)}")
```

---

## Структура выходных данных

Парсер возвращает список событий в формате:

```json
[
  {
    "bk": "LigaStavok",
    "match": "Команда 1 vs Команда 2",
    "team1": "Команда 1",
    "team2": "Команда 2",
    "tournament": "Название лиги",
    "category": "Страна",
    "sport": "Футбол",
    "start_time": "2025-01-15T18:00:00",
    "status": "prematch",
    "event_id": 12345678,
    "odds": {
      "main": {
        "1": 2.15,
        "X": 3.40,
        "2": 3.20
      },
      "totals": [
        {"type": "over", "value": 2.5, "odd": 1.85},
        {"type": "under", "value": 2.5, "odd": 1.95}
      ],
      "handicaps": []
    },
    "timestamp": "2025-01-15T12:00:00",
    "url": "https://www.ligastavok.ru/line/12345678"
  }
]
```

---

## Возможные проблемы и решения

### Ошибка 403 Forbidden
**Причина:** Куки устарели или защита QRATOR заблокировала запрос  
**Решение:** Получите свежие куки через браузер

### Пустой список событий
**Причина:** API изменилось или неверные куки  
**Решение:** 
1. Проверьте куки в браузере
2. Обновите селекторы/API эндпоинты в коде

### Браузер не запускается
**Причина:** Не установлен Chromium  
**Решение:** `playwright install chromium`

---

## API эндпоинты Лиги Ставок

| Метод | URL | Назначение |
|-------|-----|------------|
| POST | `/rest/events/v8/eventsList` | Список событий |
| POST | `/rest/events/v8/actionLines` | Коэффициенты для нескольких событий |
| POST | `/rest/events/v6/actionLine` | Детальная линия для одного события |
| WS | `/ws` | WebSocket для live-обновлений |

Базовый хост API: `https://lds-api-sites.ligastavok.ru`

---

## Поддержка WebSocket (live-обновления)

Для получения обновлений коэффициентов в реальном времени используйте WebSocket:

```python
import websockets
import json

async def subscribe_to_events(event_ids):
    uri = "wss://lds-api-sites.ligastavok.ru/ws"
    
    async with websockets.connect(uri) as websocket:
        # Подписка на обновления
        subscribe_msg = {
            "id": 55,
            "jsonrpc": "2.0",
            "meta": {"applicationName": "mobile"},
            "method": "subscribe",
            "params": {
                "method": "/notifications/v3/eventUpdated",
                "args": {"ids": [str(id) for id in event_ids]}
            }
        }
        
        await websocket.send(json.dumps(subscribe_msg))
        
        # Получение обновлений
        async for message in websocket:
            data = json.loads(message)
            print(f"Обновление: {data}")
```
