#!/usr/bin/env python3
"""
Парсер для BetBoom (betboom.ru)
API: https://siteapi.betboom.ru/api/site_api/v1
Статус: ТРЕБУЕТСЯ НАСТРОЙКА (Cloudflare + авторизация)
"""

import requests
import json
import time
from datetime import datetime

class BetBoomParser:
    def __init__(self):
        self.base_url = "https://siteapi.betboom.ru/api/site_api/v1"
        self.session = requests.Session()
        self.setup_headers()
        self.events = []
        
    def setup_headers(self):
        """Настройка заголовков"""
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru,en;q=0.9',
            'Referer': 'https://betboom.ru/',
            'Origin': 'https://betboom.ru',
        })
    
    def set_cookies(self, cookies_dict):
        """Установка cookies вручную (если есть)"""
        self.session.cookies.update(cookies_dict)
        
    def get_sports(self):
        """Получение списка видов спорта"""
        try:
            resp = self.session.get(f"{self.base_url}/sports", timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Ошибка получения спорта: {e}")
        return None
    
    def get_events(self, sport_id=None, only_live=False):
        """Получение событий"""
        endpoint = "live/events" if only_live else "events"
        url = f"{self.base_url}/{endpoint}"
        
        params = {}
        if sport_id:
            params['sport_id'] = sport_id
            
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.events = data.get('events', [])
                return self.events
        except Exception as e:
            print(f"Ошибка получения событий: {e}")
        return []
    
    def get_event_odds(self, event_id):
        """Получение коэффициентов для события"""
        try:
            url = f"{self.base_url}/events/{event_id}/odds"
            resp = self.session.get(url, timeout=10)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            print(f"Ошибка получения коэффициентов: {e}")
        return None
    
    def parse_main_markets(self, event):
        """Извлечение основных рынков из события"""
        markets = event.get('markets', [])
        result = {}
        
        for market in markets:
            market_name = market.get('name', '').lower()
            if '1x2' in market_name or 'исход' in market_name:
                result['1x2'] = [
                    {'name': r.get('name'), 'odd': r.get('price')} 
                    for r in market.get('runners', [])
                ]
            elif 'тотал' in market_name or 'total' in market_name:
                result['totals'] = [
                    {'name': r.get('name'), 'odd': r.get('price'), 'handicap': market.get('handicap')}
                    for r in market.get('runners', [])
                ]
            elif 'фора' in market_name or 'handicap' in market_name:
                result['handicaps'] = [
                    {'name': r.get('name'), 'odd': r.get('price'), 'handicap': r.get('handicap')}
                    for r in market.get('runners', [])
                ]
                
        return result
    
    def print_events(self, limit=10):
        """Вывод событий в консоль"""
        if not self.events:
            print("📭 Нет событий для отображения")
            return
            
        print(f"\n{'='*70}")
        print(f"🎲 BETBOOM - Найдено событий: {len(self.events)}")
        print(f"{'='*70}")
        
        for i, event in enumerate(self.events[:limit]):
            name = event.get('name', 'N/A')
            start_time = event.get('kickoff')
            if start_time:
                start_time = datetime.fromtimestamp(start_time/1000).strftime('%Y-%m-%d %H:%M')
            
            competitors = event.get('competitors', [])
            teams = " vs ".join([c.get('name', '?') for c in competitors[:2]])
            
            league = event.get('league', {}).get('name', 'N/A')
            betline = event.get('betline', 'prematch')
            live_status = event.get('liveStatus', {})
            score = live_status.get('score', '-')
            
            print(f"\n{i+1}. [{betline.upper()}] {teams}")
            print(f"   🏆 {league} | ⏰ {start_time or 'N/A'}")
            print(f"   📊 Счет: {score}")
            
            # Коэффициенты
            markets = self.parse_main_markets(event)
            if '1x2' in markets:
                odds_str = " | ".join([f"{r['name']}: {r['odd']}" for r in markets['1x2'][:3]])
                print(f"   💰 1X2: {odds_str}")
                
        if len(self.events) > limit:
            print(f"\n... и еще {len(self.events) - limit} событий")


def main():
    print("🚀 BetBoom Parser")
    print("="*60)
    
    parser = BetBoomParser()
    
    # Попытка получить события
    print("\n📡 Получение LIVE событий...")
    live_events = parser.get_events(only_live=True)
    
    if live_events:
        parser.print_events(limit=10)
    else:
        print("⚠️ Не удалось получить события.")
        print("💡 Возможно требуется:")
        print("   1. Получить cookies через браузер (DevTools → Application → Cookies)")
        print("   2. Установить их: parser.set_cookies({...})")
        print("   3. Или использовать Playwright для автоматического обхода Cloudflare")
    
    # Пример установки cookies вручную:
    # parser.set_cookies({
    #     'cf_clearance': 'your_token_here',
    #     '__cf_bm': 'your_token_here',
    # })


if __name__ == "__main__":
    main()
