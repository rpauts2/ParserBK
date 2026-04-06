#!/usr/bin/env python3
"""
API Hunter v2.0 - Универсальный искатель API для букмекерских контор
Автоматически запускает браузер, перехватывает ВСЕ сетевые запросы,
анализирует JS-файлы на наличие эндпоинтов и сохраняет полную информацию.
"""

import json
import time
import re
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from playwright.sync_api import sync_playwright

# Настройки
TARGET_SITES = {
    "melbet": "https://melbet.ru",
    "betboom": "https://betboom.ru",
}

OUTPUT_DIR = "discovered_apis"
os.makedirs(OUTPUT_DIR, exist_ok=True)

class APICollector:
    def __init__(self, site_name, url):
        self.site_name = site_name
        self.base_url = url
        self.requests = []
        self.responses = []
        self.js_files = []
        self.start_time = datetime.now()
        
    def analyze_request(self, request):
        """Анализ запроса"""
        url = request.url
        method = request.method
        
        # Фильтруем только интересные запросы
        parsed = urlparse(url)
        
        # Пропускаем статику (картинки, шрифты, трекинг)
        if any(ext in url.lower() for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.woff', '.ttf', '.eot']):
            return
        if 'tracking' in url or 'analytics' in url or 'telemetry' in url:
            return
            
        req_data = {
            'timestamp': time.time(),
            'url': url,
            'method': method,
            'headers': dict(request.headers),
            'post_data': request.post_data,
            'resource_type': request.resource_type,
            'is_xhr_fetch': request.resource_type in ['xhr', 'fetch'],
            'query_params': parse_qs(parsed.query),
            'path': parsed.path,
            'domain': parsed.netloc
        }
        
        self.requests.append(req_data)
        print(f"[REQ] {method} {url[:150]}...")
        
    def analyze_response(self, response):
        """Анализ ответа"""
        url = response.url
        status = response.status
        
        # Пропускаем неудачные запросы
        if status >= 400:
            return
            
        resp_data = {
            'timestamp': time.time(),
            'url': url,
            'status': status,
            'headers': dict(response.headers),
            'content_type': response.headers.get('content-type', ''),
            'body_preview': None,
            'json_data': None
        }
        
        # Пытаемся получить тело ответа для JSON и JS
        try:
            content_type = response.headers.get('content-type', '').lower()
            if 'application/json' in content_type:
                try:
                    json_data = response.json()
                    resp_data['json_data'] = json_data
                    # Краткое превью
                    if isinstance(json_data, dict):
                        keys = list(json_data.keys())[:10]
                        resp_data['body_preview'] = f"JSON with keys: {keys}"
                    elif isinstance(json_data, list):
                        resp_data['body_preview'] = f"JSON array with {len(json_data)} items"
                except:
                    pass
            elif 'javascript' in content_type or url.endswith('.js'):
                try:
                    text = response.text()
                    self.js_files.append({'url': url, 'content': text})
                    resp_data['body_preview'] = f"JS file ({len(text)} bytes)"
                except:
                    pass
        except Exception as e:
            resp_data['error'] = str(e)
            
        self.responses.append(resp_data)
        if resp_data['body_preview']:
            print(f"[RES] {status} {url[:100]}... -> {resp_data['body_preview'][:80]}")

    def perform_actions(self, page):
        """Выполняет действия на странице для триггера API"""
        print("🖱️ Выполняю действия на странице...")
        
        try:
            # Ждем загрузки
            page.wait_for_load_state('networkidle', timeout=15000)
            time.sleep(2)
            
            # Скролл вниз
            print("  - Скролл страницы...")
            for _ in range(3):
                page.mouse.wheel(0, 500)
                time.sleep(0.5)
                
            # Клики по возможным вкладкам (Live, Line, Топ и т.д.)
            selectors = [
                'a[href*="live"]', 'a[href*="line"]', 
                'button:has-text("Live")', 'button:has-text("Линия")',
                '.tab-live', '.tab-line', '.nav-live', '.nav-line',
                '[data-testid*="live"]', '[data-testid*="line"]',
                'a:has-text("LIVE")', 'a:has-text("ЛИНИЯ")'
            ]
            
            for selector in selectors:
                try:
                    elements = page.query_selector_all(selector)
                    if elements:
                        print(f"  - Найдено элементов по '{selector}': {len(elements)}")
                        elements[0].click(timeout=2000)
                        time.sleep(2)
                        page.wait_for_load_state('networkidle', timeout=10000)
                        break
                except:
                    continue
                    
            # Еще скролл
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            
            # Попытка найти и кликнуть популярные виды спорта
            sport_selectors = [
                '.sport-item', '.sport-card', '[data-sport]', 
                'a[href*="football"]', 'a[href*="tennis"]',
                'span:has-text("Футбол")', 'span:has-text("Теннис")'
            ]
            
            for selector in sport_selectors:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.click(timeout=2000)
                        time.sleep(2)
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"⚠️ Ошибка при выполнении действий: {e}")

    def extract_endpoints_from_js(self):
        """Извлекает потенциальные API эндпоинты из JS файлов"""
        endpoints = set()
        
        # Паттерны для поиска URL
        patterns = [
            r'https?://[^\s\'\"<>]+\.(ru|com|net|org)[^\s\'\"<>]*',
            r'/api/[^\s\'\"<>]+',
            r'["\'](/api/[^"\']+)',
            r'["\'](https?://[^\s\'\"<>]+)',
            r'url:\s*["\']([^"\']+)',
            r'fetch\(["\']([^"\']+)',
            r'axios\.(get|post)\(["\']([^"\']+)',
        ]
        
        for js_file in self.js_files:
            content = js_file['content']
            for pattern in patterns:
                matches = re.findall(pattern, content)
                for match in matches:
                    if isinstance(match, tuple):
                        match = match[-1] # Берем последнюю группу захвата
                    url = match.strip('"\'')
                    if url.startswith('/') and not url.startswith('//'):
                        # Относительный путь, добавляем домен
                        base_domain = urlparse(self.base_url).netloc
                        url = f"https://{base_domain}{url}"
                    if url.startswith('http') and 'api' in url.lower():
                        endpoints.add(url)
                        
        return list(endpoints)

    def run(self, headless=True):
        """Запуск сбора данных"""
        print(f"🚀 Запуск API Hunter для {self.site_name} ({self.base_url})")
        print("=" * 60)
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36'
            )
            page = context.new_page()
            
            # Подписка на события
            page.on('request', self.analyze_request)
            page.on('response', self.analyze_response)
            
            # Переход на сайт
            print(f"🌐 Открытие {self.base_url}")
            try:
                page.goto(self.base_url, wait_until='domcontentloaded', timeout=30000)
            except Exception as e:
                print(f"⚠️ Ошибка загрузки страницы: {e}")
                
            # Выполнение действий
            self.perform_actions(page)
            
            # Дополнительное ожидание
            print("⏳ Ожидание завершения сетевой активности...")
            page.wait_for_timeout(10000)
            
            browser.close()
            
        # Анализ JS файлов
        print("\n🔍 Анализ JS файлов на наличие эндпоинтов...")
        js_endpoints = self.extract_endpoints_from_js()
        if js_endpoints:
            print(f"  Найдено {len(js_endpoints)} потенциальных API в JS:")
            for ep in js_endpoints[:10]:
                print(f"    - {ep}")
                
        # Сохранение результатов
        self.save_results(js_endpoints)
        
    def save_results(self, js_endpoints):
        """Сохранение всех данных"""
        timestamp = self.start_time.strftime("%Y%m%d_%H%M%S")
        filename = f"{OUTPUT_DIR}/{self.site_name}_full_{timestamp}.json"
        
        # Фильтрация и группировка API запросов
        api_requests = [r for r in self.requests if r['is_xhr_fetch'] or 'api' in r['url'].lower()]
        api_responses = [r for r in self.responses if 'api' in r['url'].lower() or r.get('json_data')]
        
        # Уникальные домены API
        api_domains = set()
        for req in api_requests:
            api_domains.add(req['domain'])
            
        report = {
            'site': self.site_name,
            'base_url': self.base_url,
            'scan_time': self.start_time.isoformat(),
            'summary': {
                'total_requests': len(self.requests),
                'total_responses': len(self.responses),
                'api_requests': len(api_requests),
                'api_responses': len(api_responses),
                'js_files_analyzed': len(self.js_files),
                'endpoints_found_in_js': len(js_endpoints),
                'unique_api_domains': list(api_domains)
            },
            'api_requests': api_requests,
            'api_responses': api_responses,
            'js_endpoints': js_endpoints,
            'all_requests': self.requests,
            'all_responses': self.responses
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
            
        # Краткий отчет
        print("\n" + "=" * 60)
        print(f"💾 Данные сохранены в: {filename}")
        print(f"📊 Итого:")
        print(f"   Всего запросов: {len(self.requests)}")
        print(f"   API запросов: {len(api_requests)}")
        print(f"   Найдено эндпоинтов в JS: {len(js_endpoints)}")
        print(f"   Уникальные API домены: {', '.join(api_domains)}")
        print("=" * 60)

def main():
    print("🔍 API HUNTER v2.0 - Автоматический поиск API букмекеров")
    print("=" * 60)
    
    # Запуск для всех сайтов из списка
    for site_name, url in TARGET_SITES.items():
        print(f"\n>>> Сканирование: {site_name.upper()} ({url})")
        collector = APICollector(site_name, url)
        collector.run(headless=True)
        time.sleep(2)
        
    print("\n✅ Сканирование завершено! Проверьте папку 'discovered_apis/'")

if __name__ == "__main__":
    main()
