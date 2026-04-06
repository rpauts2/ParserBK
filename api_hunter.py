#!/usr/bin/env python3
"""
API Hunter Lite - Поиск API endpoints без использования браузера.
Анализирует JS-файлы, сетевые запросы через requests и публичные данные.
Работает в условиях ограниченных ресурсов.
"""

import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("❌ requests не установлен. Установка...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests

# Конфигурация целевых БК
TARGETS = {
    "melbet": {
        "url": "https://melbet.ru",
        "api_domains": ["melbet.ru", "static.melbet.com", "cdn.melbet.com"],
        "js_patterns": [r'/api/', r'api\.melbet', r'endpoints?', r'\/v\d+\/'],
        "pages_to_scan": ["/", "/live", "/line", "/football"]
    },
    "betboom": {
        "url": "https://betboom.ru",
        "api_domains": ["betboom.ru", "api.betboom.ru"],
        "js_patterns": [r'/api/', r'betboom.*api', r'\/v\d+\/', r'graphql'],
        "pages_to_scan": ["/", "/live", "/sports"]
    },
    "tenisi": {
        "url": "https://tenisi.ru",
        "api_domains": ["tenisi.ru", "api.tenisi.ru"],
        "js_patterns": [r'/api/', r'tenisi.*api', r'\/v\d+\/'],
        "pages_to_scan": ["/", "/line", "/live"]
    }
}


class APIScraper:
    def __init__(self, output_dir="discovered_apis"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.session = requests.Session()
        self.setup_session()
        self.found_apis = []
        
    def setup_session(self):
        """Настройка сессии для обхода базовых защит"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36',
            'Accept': '*/*',
            'Accept-Language': 'ru,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        retry = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def extract_js_urls(self, html, base_url):
        """Извлекает URL JavaScript файлов из HTML"""
        js_urls = []
        
        # Паттерны для поиска JS файлов
        patterns = [
            r'<script[^>]+src=[\"\'"]([^\"\'\s>]+\.js)[^>]*>',
            r'<script[^>]+src=[\"\'"]([^\"\'\s>]+/bundle[^\"\']*)[\"\'"]',
            r'<script[^>]+src=[\"\'"]([^\"\'\s>]+/main[^\"\']*)[\"\'"]',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for match in matches:
                if not match.startswith('http'):
                    match = urljoin(base_url, match)
                if match not in js_urls:
                    js_urls.append(match)
                    
        return js_urls

    def extract_api_from_js(self, js_content, domain):
        """Извлекает потенциальные API endpoints из JS кода"""
        apis = []
        
        # Паттерны для поиска API URL
        patterns = [
            r'[\"\']((?:https?://)?(?:api\.)?' + re.escape(domain.split('/')[0]) + r'(?:/[^\s\"\']+))',
            r'fetch\([\"\'](/api[^\s\"\']+)[\"\']',
            r'axios\.[a-z]+\([\"\'](/api[^\s\"\']+)[\"\']',
            r'endpoint:\s*[\"\'](/[^\s\"\']+api[^\s\"\']*)[\"\']',
            r'url:\s*[\"\'](/api[^\s\"\']+)[\"\']',
            r'/api/v\d+/[^\s\"\')\],]+',
            r'/v\d+/[^\s\"\')\],]+',
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, js_content, re.IGNORECASE)
            for match in matches:
                if len(match) > 5 and len(match) < 200:
                    # Очистка URL
                    url = match.replace('\\/', '/').strip('"\'')
                    if url not in apis and ('api' in url.lower() or '/v' in url):
                        apis.append(url)
                        
        return apis

    def scan_page(self, url, target_name, config):
        """Сканирует страницу на наличие API"""
        print(f"  📄 Сканирование: {url}")
        found = []
        
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return found
                
            html = response.text
            
            # 1. Извлекаем JS файлы
            js_urls = self.extract_js_urls(html, url)
            print(f"     Найдено JS файлов: {len(js_urls)}")
            
            # 2. Анализируем каждый JS файл
            for js_url in js_urls[:10]:  # Макс 10 файлов
                try:
                    js_resp = self.session.get(js_url, timeout=10)
                    if js_resp.status_code == 200:
                        js_content = js_resp.text
                        apis = self.extract_api_from_js(js_content, config['url'])
                        found.extend(apis)
                except Exception as e:
                    pass
                    
            # 3. Ищем API прямо в HTML
            html_apis = self.extract_api_from_js(html, config['url'])
            found.extend(html_apis)
            
        except Exception as e:
            print(f"     ⚠️ Ошибка: {e}")
            
        return list(set(found))  # Удаление дубликатов

    def guess_common_endpoints(self, base_url):
        """Проверяет распространенные API endpoints"""
        common_paths = [
            '/api/v1/events',
            '/api/v2/events', 
            '/api/v1/line',
            '/api/v2/line',
            '/api/v1/live',
            '/api/v2/live',
            '/api/events/list',
            '/api/line/list',
            '/api/sports',
            '/api/matches',
            '/api/odds',
            '/api/bets',
            '/rest/api/events',
            '/gateway/api/events',
        ]
        
        found = []
        domain = urlparse(base_url).netloc
        
        for path in common_paths:
            url = f"https://{domain}{path}"
            try:
                resp = self.session.get(url, timeout=5)
                if resp.status_code == 200:
                    content_type = resp.headers.get('content-type', '')
                    if 'json' in content_type:
                        found.append({'url': url, 'method': 'GET', 'status': 200})
                        print(f"  ✅ Найден API: {url}")
            except:
                pass
                
        return found

    def hunt(self, name, config):
        """Запускает поиск API для конкретного сайта"""
        print(f"\n{'='*60}")
        print(f"🎯 ПОИСК API: {name.upper()}")
        print(f"📍 Базовый URL: {config['url']}")
        print(f"{'='*60}")
        
        all_apis = []
        
        # 1. Сканирование страниц
        for page in config.get('pages_to_scan', ['/']):
            full_url = urljoin(config['url'], page)
            apis = self.scan_page(full_url, name, config)
            all_apis.extend(apis)
            
        # 2. Проверка распространенных endpoints
        common = self.guess_common_endpoints(config['url'])
        all_apis.extend([c['url'] for c in common])
        
        # Сохранение результатов
        self.save_results(name, config, all_apis)
        
    def save_results(self, name, config, apis):
        """Сохраняет найденные API в файл"""
        filename = self.output_dir / f"{name}_api_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        result = {
            'target': name,
            'timestamp': datetime.now().isoformat(),
            'base_url': config['url'],
            'total_found': len(apis),
            'api_endpoints': [
                {
                    'url': api,
                    'method': 'GET',
                    'source': 'js_analysis'
                }
                for api in apis
            ],
            'recommended_next_steps': [
                "Открыть URL в браузере для анализа структуры ответа",
                "Использовать curl или Postman для тестирования",
                "Проверить заголовки авторизации в DevTools"
            ]
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
            
        print(f"\n💾 Результаты сохранены в: {filename}")
        print(f"📊 Найдено потенциальных API: {len(apis)}")
        
        if apis:
            print("\n🔥 Топ-10 наиболее вероятных API endpoints:")
            for i, api in enumerate(apis[:10], 1):
                print(f"  {i}. {api}")
        else:
            print("\n⚠️ API не найдены автоматически.")
            print("   Попробуйте открыть сайт в браузере и проверить Network tab в DevTools.")


def main():
    print("🚀 API HUNTER LITE - Поиск API без браузера")
    print("="*60)
    
    scraper = APIScraper()
    
    for name, config in TARGETS.items():
        try:
            scraper.hunt(name, config)
        except Exception as e:
            print(f"❌ Ошибка при сканировании {name}: {e}")
            
    print("\n✅ Поиск завершен!")
    print(f"📁 Проверьте папку: {scraper.output_dir.absolute()}")
    print("\n💡 Совет: Для более точного анализа используйте браузер с DevTools")


if __name__ == "__main__":
    main()
