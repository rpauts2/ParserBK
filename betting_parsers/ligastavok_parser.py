"""
Рабочий парсер Лиги Ставок (Liga Stavok)
ПРИМЕЧАНИЕ: Для работы требуется либо:
  1. Установленный Playwright браузер (playwright install chromium)
  2. Либо готовые куки от реального браузера
  3. Либо сервис решения капчи (CapSolver и т.д.)

Защита QRATOR требует выполнения JavaScript, поэтому простые HTTP запросы не работают.
"""

import asyncio
import json
import uuid
import time
import random
from datetime import datetime
from typing import Optional, List, Dict, Any
from pathlib import Path

import aiohttp


class LigaStavokParser:
    """
    Парсер Лиги Ставок с использованием официального API
    
    ВАЖНО: Сайт защищен QRATOR. Для работы нужно:
    - Либо использовать Playwright для получения кук
    - Либо передать готовые куки через параметр cookies_file
    - Либо использовать прокси с уже пройденной проверкой
    """
    
    # API эндпоинты (могут меняться)
    API_HOSTS = [
        "https://lds-api-sites.ligastavok.ru",
        "https://ls-api.ligastavok.ru",
    ]
    SITE_URL = "https://www.ligastavok.ru"
    
    # Мобильный User-Agent
    MOBILE_UA = "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.6367.119 Mobile Safari/537.36"
    
    def __init__(self, proxy: Optional[str] = None, cookies_file: Optional[str] = None, use_playwright: bool = False):
        self.proxy = proxy
        self.cookies_file = cookies_file
        self.use_playwright = use_playwright
        self.session_cookies = []
        self.user_agent = self.MOBILE_UA
        self.site_url = "https://www.ligastavok.ru"
        self.api_host = self.API_HOSTS[0]
        
        # Загружаем куки из файла если указан
        if cookies_file and Path(cookies_file).exists():
            self.load_cookies(cookies_file)
    
    def load_cookies(self, filepath: str):
        """Загружает куки из JSON файла"""
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                self.session_cookies = json.load(f)
            print(f"[LigaStavok] Загружено {len(self.session_cookies)} кук из {filepath}")
        except Exception as e:
            print(f"[LigaStavok] Ошибка загрузки кук: {e}")
    
    def save_cookies(self, filepath: str):
        """Сохраняет куки в JSON файл"""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(self.session_cookies, f, ensure_ascii=False, indent=2)
            print(f"[LigaStavok] Сохранено {len(self.session_cookies)} кук в {filepath}")
        except Exception as e:
            print(f"[LigaStavok] Ошибка сохранения кук: {e}")
    
    async def get_cookies_via_playwright(self) -> List[Dict]:
        """
        Получение кук через Playwright (обходит QRATOR)
        """
        if not self.use_playwright:
            print("[LigaStavok] Playwright отключен, пробуем HTTP запрос...")
            return await self._get_cookies_http()
        
        print("[LigaStavok] Попытка получения кук через Playwright...")
        try:
            from playwright.async_api import async_playwright
            from playwright_stealth import stealth_async
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-dev-shm-usage',
                        '--disable-accelerated-2d-canvas',
                        '--no-first-run',
                        '--no-zygote',
                        '--disable-gpu'
                    ]
                )
                
                context = await browser.new_context(
                    user_agent=self.user_agent,
                    viewport={'width': 1920, 'height': 1080}
                )
                
                page = await context.new_page()
                await stealth_async(page)
                
                # Переходим на сайт и ждем загрузки
                await page.goto(self.site_url, wait_until='networkidle', timeout=60000)
                await asyncio.sleep(3)  # Ждем выполнения JS челленджа
                
                # Получаем куки
                cookies = await context.cookies()
                await browser.close()
                
                print(f"[LigaStavok] Получено {len(cookies)} кук через Playwright")
                return cookies
                
        except ImportError:
            print("[LigaStavok] Playwright не установлен, пробуем HTTP...")
            return await self._get_cookies_http()
        except Exception as e:
            print(f"[LigaStavok] Ошибка Playwright: {e}, пробуем HTTP...")
            return await self._get_cookies_http()
    
    async def _get_cookies_http(self) -> List[Dict]:
        """Получение кук через обычный HTTP запрос (может не обойти QRATOR)"""
        print("[LigaStavok] Попытка получения кук через HTTP...")
        
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
        
        try:
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(self.site_url, timeout=30, allow_redirects=True) as response:
                    cookies = []
                    for cookie_name, morsel in response.cookies.items():
                        cookies.append({
                            "name": cookie_name,
                            "value": morsel.value,
                            "domain": "ligastavok.ru",
                            "path": "/"
                        })
                    print(f"[LigaStavok] Получено {len(cookies)} кук (может быть недостаточно для обхода QRATOR)")
                    return cookies
        except Exception as e:
            print(f"[LigaStavok] Ошибка при получении кук: {e}")
            return []
    
    def _get_headers(self) -> Dict[str, str]:
        """Возвращает заголовки для API запросов"""
        # Добавляем случайный x-req-id для каждого запроса
        return {
            "Content-Type": "application/json",
            "x-application-name": "mobile",
            "x-req-id": str(uuid.uuid4()),
            "User-Agent": self.user_agent,
            "Accept": "*/*",
            "Accept-Language": "ru-RU,ru;q=0.9",
        }
    
    async def _make_request(self, endpoint: str, payload: Dict) -> Optional[Dict]:
        """Делает POST запрос к API"""
        url = f"{self.api_host}{endpoint}"
        headers = self._get_headers()
        
        # Добавляем куки если есть
        if self.session_cookies:
            cookies_str = "; ".join([f"{c['name']}={c['value']}" for c in self.session_cookies])
            headers["Cookie"] = cookies_str
        
        # Настройка прокси
        connector = None
        if self.proxy:
            from aiohttp_socks import ProxyConnector
            try:
                connector = ProxyConnector.from_url(self.proxy)
            except:
                connector = aiohttp.TCPConnector()
        
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            try:
                # Добавляем случайную задержку
                await asyncio.sleep(random.uniform(0.5, 2.0))
                
                async with session.post(url, json=payload, timeout=30) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data
                    else:
                        print(f"[LigaStavok] Ошибка API: {response.status}")
                        # Пробуем обновить куки при ошибке 403
                        if response.status == 403:
                            print("[LigaStavok] Получен 403, пробуем обновить куки...")
                            self.session_cookies = await self.get_cookies_via_playwright()
                        return None
            except Exception as e:
                print(f"[LigaStavok] Ошибка запроса: {e}")
                return None
    
    async def get_events_list(self, limit: int = 100, skip: int = 0, view: str = "priority") -> List[Dict]:
        """
        Получает список событий через eventsList API
        """
        payload = {
            "gameId": [],  # все виды спорта
            "limit": limit,
            "skip": skip,
            "topEvents": False,
            "ts": int(time.time() * 1000),
            "view": view,
            "widgetVideo": False,
            "proposedTypes": ["MAINOFFER"]
        }
        
        result = await self._make_request("/rest/events/v8/eventsList", payload)
        
        if result and result.get("result"):
            return result["result"].get("data", [])
        return []
    
    async def get_action_lines(self, event_ids: List[int]) -> Dict:
        """
        Получает коэффициенты для списка событий
        """
        payload = {
            "ids": event_ids,
            "ts": int(time.time() * 1000),
            "proposedTypes": ["MAINOFFER"]
        }
        
        result = await self._make_request("/rest/events/v8/actionLines", payload)
        
        if result and result.get("result"):
            return result["result"].get("data", {})
        return {}
    
    async def get_single_event_line(self, event_id: int) -> Optional[Dict]:
        """
        Получает детальную линию для одного события
        """
        payload = {
            "id": event_id,
            "ts": int(time.time() * 1000),
            "proposedTypes": ["MAINOFFER"]
        }
        
        result = await self._make_request("/rest/events/v6/actionLine", payload)
        
        if result and result.get("result"):
            return result["result"]
        return None
    
    def _normalize_team_name(self, name: str) -> str:
        """Нормализует название команды"""
        # Убираем лишние пробелы, приводим к стандартному виду
        return " ".join(name.strip().split())
    
    def _extract_main_odds(self, event: Dict) -> Dict[str, Any]:
        """
        Извлекает основные коэффициенты (1X2, Тоталы, Форы) из события
        """
        odds_data = {
            "1": None,
            "X": None,
            "2": None,
            "totals": [],
            "handicaps": []
        }
        
        outcomes = event.get("outcomes", {})
        markets = event.get("markets", {})
        
        # Ищем основные исходы 1X2
        for outcome_key, outcome in outcomes.items():
            title = outcome.get("title", "")
            value = outcome.get("value")
            ad_value = outcome.get("adValue")
            market_id = outcome.get("marketId")
            
            if not value:
                continue
            
            # Основные исходы
            if title == "1":
                odds_data["1"] = float(value)
            elif title == "X":
                odds_data["X"] = float(value)
            elif title == "2":
                odds_data["2"] = float(value)
            
            # Тоталы
            elif title in ["Мен", "Меньше", "Under", "ТМ"]:
                odds_data["totals"].append({
                    "type": "under",
                    "value": float(ad_value) if ad_value else None,
                    "odd": float(value)
                })
            elif title in ["Бол", "Больше", "Over", "ТБ"]:
                odds_data["totals"].append({
                    "type": "over",
                    "value": float(ad_value) if ad_value else None,
                    "odd": float(value)
                })
            
            # Форы
            elif title.startswith("Ф") or title.startswith("H"):
                handicap_val = None
                if ad_value:
                    try:
                        handicap_val = float(ad_value)
                    except:
                        pass
                odds_data["handicaps"].append({
                    "type": "handicap",
                    "value": handicap_val,
                    "odd": float(value),
                    "team": "1" if "1" in title else "2"
                })
        
        return odds_data
    
    async def parse_all_events(self, max_pages: int = 3) -> List[Dict[str, Any]]:
        """
        Парсит все доступные события с пагинацией
        """
        all_events = []
        
        for page in range(max_pages):
            skip = page * 100
            print(f"[LigaStavok] Загрузка страницы {page + 1}/{max_pages} (skip={skip})...")
            
            events = await self.get_events_list(limit=100, skip=skip, view="all")
            
            if not events:
                print(f"[LigaStavok] Нет больше событий на странице {page + 1}")
                break
            
            for event in events:
                try:
                    event_data = self._parse_single_event(event)
                    if event_data:
                        all_events.append(event_data)
                except Exception as e:
                    print(f"[LigaStavok] Ошибка парсинга события {event.get('id')}: {e}")
                    continue
            
            # Небольшая задержка между страницами
            await asyncio.sleep(1)
        
        return all_events
    
    def _parse_single_event(self, event: Dict) -> Optional[Dict[str, Any]]:
        """
        Парсит одно событие в стандартный формат
        """
        try:
            event_info = event.get("event", {})
            
            team1 = event_info.get("team1", "")
            team2 = event_info.get("team2", "")
            
            if not team1 or not team2:
                return None
            
            tournament = event_info.get("tournamentTitle", "")
            category = event_info.get("categoryTitle", "")
            start_time = event_info.get("startDate", 0)
            status = event_info.get("ns", "prematch")  # prematch или live
            
            # Извлекаем коэффициенты
            odds = self._extract_main_odds(event)
            
            # Формируем результат
            result = {
                "bk": "LigaStavok",
                "match": f"{self._normalize_team_name(team1)} vs {self._normalize_team_name(team2)}",
                "team1": self._normalize_team_name(team1),
                "team2": self._normalize_team_name(team2),
                "tournament": tournament,
                "category": category,
                "sport": event_info.get("gameTitle", "Футбол"),
                "start_time": datetime.fromtimestamp(start_time / 1000).isoformat() if start_time else None,
                "status": status,
                "event_id": event.get("id"),
                "odds": {
                    "main": {
                        "1": odds["1"],
                        "X": odds["X"],
                        "2": odds["2"]
                    },
                    "totals": odds["totals"],
                    "handicaps": odds["handicaps"]
                },
                "timestamp": datetime.now().isoformat(),
                "url": f"{self.SITE_URL}/line/{event.get('id')}"
            }
            
            return result
            
        except Exception as e:
            print(f"[LigaStavok] Ошибка при парсинге события: {e}")
            return None
    
    async def initialize(self):
        """Инициализация - получение кук"""
        self.session_cookies = await self.get_cookies_via_playwright()
    
    async def run(self, output_file: str = "ligastavok_odds.json", use_playwright: bool = False) -> List[Dict]:
        """
        Основной метод запуска парсера
        
        Args:
            output_file: Файл для сохранения результатов
            use_playwright: Использовать ли Playwright для обхода защиты
        """
        print("=" * 60)
        print("ПАРСЕР ЛИГА СТАВОК - ЗАПУСК")
        print("=" * 60)
        
        # Устанавливаем флаг использования Playwright
        self.use_playwright = use_playwright
        
        # Инициализация (получение кук)
        await self.initialize()
        
        # Проверяем есть ли куки
        if not self.session_cookies:
            print("[LigaStavok] ВНИМАНИЕ: Не удалось получить куки. Пробуем запрос без кук...")
        
        # Парсинг всех событий
        events = await self.parse_all_events(max_pages=2)
        
        # Сохранение результата
        if events:
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(events, f, ensure_ascii=False, indent=2)
            print(f"\n[LigaStavok] Сохранено {len(events)} событий в {output_file}")
        else:
            print("\n[LigaStavok] Не удалось получить события")
        
        return events


async def main():
    # Пробуем запустить с Playwright (если браузер установлен)
    # Если нет - автоматически переключится на HTTP режим
    parser = LigaStavokParser()
    
    try:
        # Запускаем с флагом use_playwright=False для тестирования без браузера
        # Если у вас установлен браузер, измените на use_playwright=True
        events = await parser.run(use_playwright=False)
        
        # Вывод первых 5 событий для демонстрации
        print("\n" + "=" * 60)
        print("ПРИМЕРЫ СОБЫТИЙ:")
        print("=" * 60)
        
        if events:
            for i, event in enumerate(events[:5], 1):
                print(f"\n{i}. {event['match']}")
                print(f"   Турнир: {event['tournament']}")
                print(f"   Время: {event['start_time']}")
                print(f"   Коэффициенты: 1={event['odds']['main']['1']}, X={event['odds']['main']['X']}, 2={event['odds']['main']['2']}")
            
            print("\n" + "=" * 60)
            print(f"ВСЕГО СОБЫТИЙ: {len(events)}")
            print("=" * 60)
        else:
            print("\n[LigaStavok] События не найдены. Возможные причины:")
            print("  1. Защита QRATOR блокирует запросы без валидных кук")
            print("  2. API эндпоинты изменились")
            print("  3. Требуется использование реального браузера (Playwright)")
            print("\nРекомендации:")
            print("  - Установите браузер: playwright install chromium")
            print("  - Или передайте готовые куки: LigaStavokParser(cookies_file='cookies.json')")
            print("  - Или используйте прокси с пройденной проверкой QRATOR")
        
    except Exception as e:
        print(f"\n[ERROR] Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
