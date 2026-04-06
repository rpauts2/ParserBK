import asyncio
import aiohttp
import time
import uuid
import json
import random
from datetime import datetime
from typing import List, Dict, Optional, Any

# --- КОНФИГУРАЦИЯ ---
CONFIG = {
    "ligastavok": {
        "api_host": "https://lds-api-sites.ligastavok.ru",
        "site_url": "https://www.ligastavok.ru",
    },
    "olimpbet": {
        "api_host": "https://bet.olimbet.com",
        "site_url": "https://www.olimbet.com",
    },
    "melbet": {
        "api_host": "https://a.melbet.com",
        "site_url": "https://melbet.ru",
    }
}

class BaseParser:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session
        # Фиксированный User-Agent последнего Chrome
        self.ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        self.headers = {
            "User-Agent": self.ua,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Content-Type": "application/json",
            "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        self.cookies = {}

    async def fetch_with_retry(self, url: str, method: str = 'GET', json_data: dict = None, headers: dict = None, params: dict = None) -> Optional[dict]:
        """Умный запрос с ретраями"""
        for attempt in range(3):
            try:
                async with self.session.request(method, url, json=json_data, headers={**self.headers, **(headers or {})}, cookies=self.cookies, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    elif resp.status in [403, 429, 503]:
                        print(f"[{self.__class__.__name__}] Блокировка ({resp.status}). Ждем {2 ** attempt} сек...")
                        await asyncio.sleep(2 ** attempt)
                    else:
                        text = await resp.text()
                        print(f"[{self.__class__.__name__}] Ошибка {resp.status}: {text[:200]}")
                        return None
            except asyncio.TimeoutError:
                print(f"[{self.__class__.__name__}] Таймаут запроса")
                await asyncio.sleep(1)
            except Exception as e:
                print(f"[{self.__class__.__name__}] Ошибка соединения: {e}")
                await asyncio.sleep(1)
        return None

    def normalize_teams(self, team1: str, team2: str) -> str:
        """Приведение названий к стандарту"""
        t1 = team1.strip().title()
        t2 = team2.strip().title()
        return f"{t1} vs {t2}"

    def parse_odds_structure(self, outcomes: dict) -> dict:
        """Извлечение основных исходов 1, X, 2"""
        odds = {"1": None, "X": None, "2": None}
        for key, val in outcomes.items():
            title = val.get("title", "")
            value = val.get("value")
            if not value: continue
            
            if title == "1": odds["1"] = float(value)
            elif title == "X": odds["X"] = float(value)
            elif title == "2": odds["2"] = float(value)
        return odds

    async def parse(self) -> List[dict]:
        raise NotImplementedError


class LigaStavokParser(BaseParser):
    """Парсер Лиги Ставок - используем API линии (аналогично 24bet)"""
    
    def __init__(self, session: aiohttp.ClientSession, cookies: dict = None):
        super().__init__(session)
        if cookies:
            self.cookies = cookies
        # Используем тот же кластер API, что и 24bet (общая линия)
        self.api_host = "https://line51.tf39be-resources.com"
        self.headers.update({
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ru,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://www.ligastavok.ru",
            "Referer": "https://www.ligastavok.ru/",
            "Sec-Ch-Ua": '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3", "Yowser";v="2.5"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "cross-site",
        })
        self.version = 0

    async def get_events(self):
        url = f"{self.api_host}/events/list"
        params = {
            "lang": "ru",
            "version": self.version,
            "scopeMarket": "3000"  # Пробуем общий рынок (как у 24bet)
        }
        
        data = await self.fetch_with_retry(url, method='GET', params=params)
        if data:
            # Обновляем версию для следующего запроса
            self.version = data.get("packetVersion", self.version)
            return data
        return None

    async def parse(self) -> List[dict]:
        results = []
        data = await self.get_events()
        
        if not data:
            print("[LigaStavok] Не удалось получить данные. Проверьте доступность API.")
            return []

        events = data.get("events", [])
        sports = data.get("sports", [])
        custom_factors = data.get("customFactors", [])
        
        # Создаем мапу коэффициентов по eventId
        odds_map = {}
        for cf in custom_factors:
            eid = cf.get("e") or cf.get("eventId")
            if eid:
                odds_map[eid] = cf.get("factors", [])

        # Создаем мапу видов спорта
        sport_map = {s["id"]: s.get("name", "Unknown") for s in sports}

        for event in events:
            # Берем только основные события (level=1)
            if event.get("level") != 1:
                continue
                
            eid = event.get("id")
            sport_id = event.get("sportId")
            team1 = event.get("team1", "Unknown")
            team2 = event.get("team2", "Unknown")
            start_time = event.get("startTime")
            place = event.get("place", "line")  # live или line
            
            # Счет для live
            score = "-"
            if place == "live":
                # Ищем счет в eventMiscs
                for misc in data.get("eventMiscs", []):
                    if misc.get("eventId") == eid:
                        s1 = misc.get("score1", 0)
                        s2 = misc.get("score2", 0)
                        score = f"{s1}:{s2}"
                        break

            # Получаем коэффициенты
            factors = odds_map.get(eid, [])
            odds = {"1": None, "X": None, "2": None, "Total Over": None, "Total Under": None, "Handicap": None}
            
            for f in factors:
                code = f.get("f")
                val = f.get("v")
                if not val: continue
                
                # Примерные коды (могут отличаться)
                if code == 910: odds["1"] = val
                elif code == 911: odds["X"] = val  # Ничья
                elif code == 912: odds["2"] = val
                elif code in [922, 974]: odds["Total Over"] = val  # Тотал больше
                elif code in [921, 976]: odds["Total Under"] = val  # Тотал меньше
            
            if any([odds["1"], odds["X"], odds["2"]]):
                results.append({
                    "bookmaker": "LigaStavok",
                    "sport": sport_map.get(sport_id, "Unknown"),
                    "league": event.get("tournamentName", "Unknown"),
                    "teams": f"{team1} vs {team2}",
                    "start_time": datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M') if start_time else "N/A",
                    "type": "LIVE" if place == "live" else "PREMATCH",
                    "score": score if place == "live" else "-",
                    "odds_1": odds["1"],
                    "odds_X": odds["X"],
                    "odds_2": odds["2"],
                    "total_over": odds["Total Over"],
                    "total_under": odds["Total Under"],
                    "event_id": eid
                })
        
        return results


class OlimpbetParser(BaseParser):
    """Парсер Olimpbet. Использует открытое API, но требует правильного Referer"""
    
    def __init__(self, session: aiohttp.ClientSession):
        super().__init__(session)
        self.api_host = "https://bet.olimbet.com" # Основной шлюз
        self.headers.update({
            "Referer": "https://www.olimbet.com/",
            "Origin": "https://www.olimbet.com"
        })

    async def parse(self) -> List[dict]:
        results = []
        # Olimpbet часто использует структуру /api/v1/events или подобную
        # Это примерный эндпоинт, реальный может отличаться (нужна отладка в Network)
        url = f"{self.api_host}/api/v1/prematch/events" 
        
        # Попытка получить данные
        data = await self.fetch_with_retry(url)
        
        if not data:
            # Альтернативный путь, если первый не сработал
            url = "https://olimbet.com/api/events/list" 
            data = await self.fetch_with_retry(url)

        if data and isinstance(data, list):
            for event in data[:10]: # Лимит для теста
                # Структура Olimpbet может отличаться, адаптируем
                home = event.get("home_team", event.get("team1", "Unknown"))
                away = event.get("away_team", event.get("team2", "Unknown"))
                
                odds_obj = event.get("odds", {})
                # Обычно ключи '1', '2', 'X' или вложенные
                main_odd_1 = odds_obj.get("1", odds_obj.get("home", {}).get("price"))
                main_odd_2 = odds_obj.get("2", odds_obj.get("away", {}).get("price"))
                main_odd_x = odds_obj.get("X", odds_obj.get("draw", {}).get("price"))

                if main_odd_1 or main_odd_2:
                    results.append({
                        "bk": "Olimpbet",
                        "match": self.normalize_teams(home, away),
                        "odds": {"1": main_odd_1, "X": main_odd_x, "2": main_odd_2},
                        "timestamp": datetime.now().isoformat()
                    })
        else:
            print("[Olimpbet] Нет данных или структура изменилась. Требуется актуализация URL API.")
            
        return results


class MelbetParser(BaseParser):
    """Парсер Melbet (структура похожа на 1xStavok)"""
    def __init__(self, session: aiohttp.ClientSession, cookies: dict = None):
        super().__init__(session)
        if cookies:
            self.cookies = cookies
        self.headers.update({
            "Referer": "https://melbet.ru/",
            "x-requested-with": "XMLHttpRequest"
        })

    async def parse(self) -> List[dict]:
        results = []
        # Melbet использует сложный API с параметрами
        url = "https://a.melbet.com/en/live_events/get_events" # Пример для Live
        # Или prematch: https://a.melbet.com/en/events/get_events
        
        params = {
            "type": "prematch",
            "mode": "all",
            "lang": "ru",
            "no_cache": str(int(time.time()))
        }
        
        data = await self.fetch_with_retry(url, headers={"Params": params}) # Упрощенно
        
        if data and "data" in data:
            events = data["data"]
            for ev in events[:5]:
                # Структура Melbet очень глубокая
                teams = ev.get("events", {}).get("data", [])
                if len(teams) >= 2:
                     # Здесь нужна сложная логика парсинга вложенности
                     # Для краткости - заглушка успешного ответа
                     results.append({
                        "bk": "Melbet",
                        "match": "Melbet Event (Demo Structure)",
                        "odds": {"1": 1.95, "X": 3.2, "2": 3.5},
                        "timestamp": datetime.now().isoformat(),
                        "note": "Требуется точный маппинг полей API Melbet"
                    })
        return results


async def main():
    print("=== ЗАПУСК ПАРСЕРА БК (LITE MODE) ===")
    
    # 1. Создаем сессию с правильными заголовками
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }
    connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300, ssl=False)
    
    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        
        parsers = [
            LigaStavokParser(session),
            OlimpbetParser(session),
        ]
        
        all_results = []
        
        for parser in parsers:
            print(f"\n--- Парсинг {parser.__class__.__name__} ---")
            try:
                data = await parser.parse()
                if data:
                    print(f"Найдено событий: {len(data)}")
                    all_results.extend(data)
                    # Вывод первого события для проверки
                    print(json.dumps(data[0], ensure_ascii=False, indent=2))
                else:
                    print("Событий не найдено или ошибка доступа.")
            except Exception as e:
                print(f"Критическая ошибка в парсере {parser.__class__.__name__}: {e}")
                import traceback
                traceback.print_exc()
        
        # Сохранение результата
        if all_results:
            with open("odds_result.json", "w", encoding="utf-8") as f:
                json.dump(all_results, f, ensure_ascii=False, indent=2)
            print(f"\n✅ Всего сохранено {len(all_results)} событий в odds_result.json")
        else:
            print("\n❌ Не удалось собрать ни одного события.")

if __name__ == "__main__":
    asyncio.run(main())
