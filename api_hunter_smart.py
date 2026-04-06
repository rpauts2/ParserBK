#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API HUNTER v2.0 - Интеллектуальный поиск API букмекерских контор
Принцип работы:
1. Запускает браузер (Playwright).
2. Переходит на сайт, кликает по разделам (Live/Line), скроллит.
3. Перехватывает ВСЕ сетевые запросы.
4. Фильтрует мусор (картинки, css, метрики, реклама).
5. Выделяет целевые API: JSON ответы, периодические обновления, ключевые слова в URL.
6. Сохраняет результат в JSON.
"""

import json
import time
import re
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from typing import List, Dict, Any, Set

try:
    from playwright.sync_api import sync_playwright, Page, Request, Response
except ImportError:
    print("❌ Ошибка: Playwright не установлен. Выполните: pip install playwright && playwright install chromium")
    exit(1)

# --- КОНФИГУРАЦИЯ ---

TARGET_SITES = {
    "melbet": "https://melbet.ru",
    "betboom": "https://betboom.ru",
    "tenisi": "https://tenisi.ru",
    # Можно добавить другие
}

# Ключевые слова, указывающие на МУСОР (реклама, метрики, статику)
BLACKLIST_KEYWORDS = [
    'google-analytics', 'googletag', 'doubleclick', 'yandex-metrica', 'metrika',
    'facebook', 'twitter', 'instagram', 'tiktok',
    'adsystem', 'adserver', 'advert', 'banner', 'promo',
    'cdn.', 'static.', 'cloudfront', 'akamai', 'fastly',
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp',
    '.css', '.woff', '.woff2', '.ttf', '.eot',
    'sentry', 'log.', 'trace', 'pixel', 'beacon',
    'fonts.googleapis', 'fonts.gstatic', 'themes.googleusercontent',
    'targetads', 'fpnpmcdn', 'varioqub', 'loader_v', 'vendor-ui'
]

# Ключевые слова, указывающие на ПОТЕНЦИАЛЬНОЕ API (Букмекерская тематика)
TARGET_KEYWORDS = [
    'api', 'line', 'live', 'event', 'match', 'game', 'sport', 'bet', 'odds', 'factor',
    'coupon', 'betslip', 'score', 'stat', 'tournament', 'championship', 'league',
    'getevents', 'getline', 'getlive', 'changes', 'version', 'vtag', 'packet',
    'siteapi', 'clientsapi', 'sport.', '/ma/', '/api-'
]

# Домены, которым доверяем (основной + поддомены)
TRUSTED_DOMAIN_PATTERNS = [
    r'.*melbet.*', r'.*betboom.*', r'.*tenisi.*', r'.*olimp.*', r'.*fon.*',
    r'.*leon.*', r'.*24bet.*', r'.*ligastavok.*', r'.*winline.*', r'.*pari.*',
    r'.*betcity.*', r'.*marathon.*', r'.*zenit.*', r'.*baltbet.*', r'.*bettery.*',
    r'.*bk.*resources.*', r'.*tf.*resources.*'
]

# --- ЛОГИКА ФИЛЬТРАЦИИ ---

def is_noise(url: str) -> bool:
    """Проверяет, является ли запрос мусором."""
    url_lower = url.lower()
    for keyword in BLACKLIST_KEYWORDS:
        if keyword in url_lower:
            return True
    return False

def is_potential_api(url: str, content_type: str, method: str) -> bool:
    """Проверяет, похож ли запрос на целевое API."""
    url_lower = url.lower()
    
    # 1. Проверка по ключевым словам
    has_target_keyword = any(kw in url_lower for kw in TARGET_KEYWORDS)
    
    # 2. Проверка типа контента (JSON - главный кандидат)
    is_json = 'json' in content_type.lower() if content_type else False
    
    # 3. Проверка метода (GET/POST обычно для API)
    is_valid_method = method in ['GET', 'POST', 'OPTIONS']
    
    # 4. Проверка домена (чтобы не ушло на сторонние сервисы)
    parsed = urlparse(url)
    domain = parsed.netloc
    is_trusted_domain = any(re.match(pattern, domain) for pattern in TRUSTED_DOMAIN_PATTERNS)
    
    # Логика решения:
    # Если JSON + наш домен -> почти наверняка API
    # Если ключевое слово + наш домен -> вероятно API
    # Если просто ключевое слово но чужой домен -> игнор
    # Если просто JSON но чужой домен (например, CDN конфиг) -> игнор
    
    if is_trusted_domain:
        if is_json:
            return True
        if has_target_keyword and is_valid_method:
            return True
            
    return False

def extract_query_params(url: str) -> Dict[str, Any]:
    """Извлекает параметры из URL для анализа."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    # Преобразуем списки в одиночные значения для читаемости
    return {k: v[0] if len(v) == 1 else v for k, v in params.items()}

# --- СБОР ДАННЫХ ---

class ApiHunter:
    def __init__(self):
        self.captured_data: List[Dict[str, Any]] = []
        self.request_times: Dict[str, List[float]] = {} # Для поиска polling-запросов
        
    def on_request(self, request: Request):
        url = request.url
        if is_noise(url):
            return
        
        # Запоминаем время запроса для анализа частоты
        now = time.time()
        if url not in self.request_times:
            self.request_times[url] = []
        self.request_times[url].append(now)
        
        # Сохраняем базовую инфу, тело ответа добавим в on_response
        data = {
            'timestamp': now,
            'url': url,
            'method': request.method,
            'headers': dict(request.headers),
            'post_data': request.post_data,
            'query_params': extract_query_params(url),
            'response_status': None,
            'response_content_type': None,
            'response_body_preview': None,
            'is_polling_candidate': False
        }
        # Временное хранилище до получения ответа
        self.temp_store[request.url + "_" + str(now)] = data

    def on_response(self, response: Response):
        request = response.request
        url = request.url
        
        if is_noise(url):
            return
            
        content_type = response.headers.get('content-type', '')
        
        if not is_potential_api(url, content_type, request.method):
            return

        # Пытаемся получить тело ответа (только если JSON или текст, чтобы не тянуть мегабайты)
        body_preview = ""
        try:
            if 'json' in content_type or 'text' in content_type or 'javascript' in content_type:
                text = response.text()
                if len(text) > 500:
                    body_preview = text[:500] + "... [truncated]"
                else:
                    body_preview = text
            else:
                body_preview = f"[Binary data: {content_type}]"
        except Exception:
            body_preview = "[Failed to read body]"

        # Ищем запись запроса
        # Так как URL могут повторяться, ищем по совпадению URL и метода в недавних
        found_key = None
        for key in list(self.temp_store.keys()):
            if key.startswith(url):
                found_key = key
                break
        
        if found_key:
            data = self.temp_store.pop(found_key)
            data['response_status'] = response.status
            data['response_content_type'] = content_type
            data['response_body_preview'] = body_preview
            
            # Анализ на polling (частые повторения)
            count = len(self.request_times.get(url, []))
            if count > 2: # Если запрос пришел более 2 раз за сессию
                data['is_polling_candidate'] = True
                data['polling_count'] = count
                
            self.captured_data.append(data)
            print(f"✅ НАЙДЕН ПОТЕНЦИАЛЬНЫЙ API: {request.method} {url}")
            if data['is_polling_candidate']:
                print(f"   ⚡ ВЫСОКИЙ ПРИОРИТЕТ: Запрос повторяется ({count} раз) - скорее всего Live/Line обновление")

    def run(self, site_name: str, url: str, duration: int = 15):
        print(f"\n🚀 Запуск API Hunter для {site_name} ({url})...")
        print(f"⏱ Время сбора: {duration} сек.")
        print("-" * 50)
        
        self.temp_store = {}
        self.captured_data = []
        self.request_times = {}

        with sync_playwright() as p:
            # Запуск браузера
            browser = p.chromium.launch(headless=False) # Headless=False чтобы видеть действия
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080}
            )
            page = context.new_page()

            # Подписка на события
            page.on('request', self.on_request)
            page.on('response', self.on_response)

            try:
                # 1. Открытие главной
                print(f"🌐 Открытие {url}...")
                page.goto(url, wait_until='networkidle', timeout=30000)
                time.sleep(3) # Ждем прогрузки JS

                # 2. Попытка найти и кликнуть "Live"
                live_selectors = [
                    'a[href*="live"]', 'button:has-text("Live")', 'button:has-text("LIVE")', 
                    '.live-tab', '[data-testid="live"]', 'span:has-text("Лайв")'
                ]
                for selector in live_selectors:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible():
                            print(f"🖱 Клик по элементу: {selector}")
                            el.click()
                            time.sleep(4) # Ждем загрузки Live данных
                            break
                    except:
                        continue

                # 3. Попытка найти и кликнуть "Линия" / "Prematch"
                line_selectors = [
                    'a[href*="line"]', 'a[href*="prematch"]', 
                    'button:has-text("Линия")', 'button:has-text("Line")',
                    '.line-tab', '[data-testid="line"]'
                ]
                for selector in line_selectors:
                    try:
                        el = page.locator(selector).first
                        if el.is_visible():
                            print(f"🖱 Клик по элементу: {selector}")
                            el.click()
                            time.sleep(4) # Ждем загрузки Line данных
                            break
                    except:
                        continue

                # 4. Скролл страницы (триггер для lazy-loading)
                print("📜 Скролл страницы...")
                for _ in range(3):
                    page.mouse.wheel(0, 500)
                    time.sleep(1)
                page.mouse.wheel(0, -1000) # Наверх
                time.sleep(2)

                # 5. Ожидание основного времени сбора
                print(f"⏳ Сбор данных в фоне ({duration} сек)...")
                # Досчитываем время, если клики заняли время
                time.sleep(max(0, duration - 10)) 

            except Exception as e:
                print(f"⚠️ Ошибка при навигации: {e}")
            finally:
                browser.close()

        # Обработка результатов
        self.save_results(site_name)

    def save_results(self, site_name: str):
        if not self.captured_data:
            print("\n⚠️ API не найдено.")
            return

        # Сортировка: сначала polling-кандидаты, потом JSON, потом остальное
        sorted_data = sorted(
            self.captured_data,
            key=lambda x: (
                -int(x.get('is_polling_candidate', False)), # Сначала те, что часто повторяются
                -1 if 'json' in (x.get('response_content_type') or '') else 0,
                -len(x.get('response_body_preview') or '')
            )
        )

        # Убираем дубликаты URL (оставляем последний/самый полный вариант)
        seen_urls = set()
        unique_data = []
        for item in reversed(sorted_data): # Идем с конца, чтобы взять свежие
            if item['url'] not in seen_urls:
                seen_urls.add(item['url'])
                unique_data.append(item)
        unique_data.reverse() # Возвращаем порядок

        filename = f"discovered_apis/{site_name}_smart_api.json"
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump({
                'scan_date': datetime.now().isoformat(),
                'site': site_name,
                'total_found': len(unique_data),
                'endpoints': unique_data
            }, f, indent=2, ensure_ascii=False)

        print("\n" + "="*50)
        print(f"💾 СОХРАНЕНО: {filename}")
        print(f"🔥 Найдено уникальных API endpoints: {len(unique_data)}")
        
        # Вывод ТОП-5 самых важных
        print("\n🏆 ТОП-5 наиболее вероятных рабочих API:")
        for i, item in enumerate(unique_data[:5], 1):
            poll_tag = " ⚡ POLLING (Live/Line)" if item.get('is_polling_candidate') else ""
            print(f"{i}. {item['method']} {item['url']}{poll_tag}")
            if item.get('query_params'):
                print(f"   Params: {item['query_params']}")

if __name__ == "__main__":
    import os
    if not os.path.exists('discovered_apis'):
        os.makedirs('discovered_apis')

    hunter = ApiHunter()
    
    # ЗАПУСК ДЛЯ НУЖНЫХ САЙТОВ
    # Можно закомментировать лишнее
    targets = [
        ("melbet", "https://melbet.ru"),
        ("betboom", "https://betboom.ru"),
        ("tenisi", "https://tenisi.ru")
    ]
    
    for name, url in targets:
        hunter.run(name, url, duration=20) # 20 секунд на сайт
        time.sleep(2) # Пауза между сайтами
