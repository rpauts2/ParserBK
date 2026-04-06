#!/usr/bin/env python3
"""
Парсер для bet-m.ru (sport.bet-m.ru)
Версия: 3.0 - ТОЛЬКО РУЧНЫЕ COOKIES (нет места для Playwright)

ВНИМАНИЕ: Из-за строгой защиты Cloudflare и ограничений окружения,
необходимо вручную получить cookies из браузера.

ИНСТРУКЦИЯ:
1. Откройте https://sport.bet-m.ru/ в своём браузере (Chrome/Firefox/Yandex)
2. Нажмите F12 → Application → Cookies → https://sport.bet-m.ru
3. Скопируйте значения: cf_clearance, __cf_bm, _cfuvid
4. Вставьте их ниже в MANUAL_COOKIES
5. Запустите: python betm_final_parser.py
"""

import requests
import uuid
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any

# ============================================================================
# 🔴 ВСТАВЬТЕ СЮДА ВАШИ COOKIES ИЗ БРАУЗЕРА
# ============================================================================
MANUAL_COOKIES = {
    'cf_clearance': '',      # Вставьте значение из браузера
    '__cf_bm': '',           # Вставьте значение из браузера
    '_cfuvid': ''            # Вставьте значение из браузера
}
# ============================================================================

BASE_URL = "https://sport.bet-m.ru"
PARTNER_ID = "3000093"
LANG_ID = "1"
COUNTRY_CODE = "NL"

class BetMParser:
    def __init__(self):
        self.session = requests.Session()
        self.unique_id = str(uuid.uuid4())
        self.partner_id = PARTNER_ID
        self.lang_id = LANG_ID
        self.country_code = COUNTRY_CODE
        self.session_token = None
        self.events_data = {}
        
        self.headers = {
            'Accept': '*/*',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'ru,en;q=0.9',
            'Content-Type': 'application/json',
            'Origin': BASE_URL,
            'Referer': f'{BASE_URL}/',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36'
        }
        
        if not self._validate_cookies():
            print("⚠️  COOKIES НЕ НАСТРОЕНЫ!")
            print("\n📋 ИНСТРУКЦИЯ:")
            print("1. Откройте https://sport.bet-m.ru/ в браузере")
            print("2. F12 → Application → Cookies")
            print("3. Скопируйте: cf_clearance, __cf_bm, _cfuvid")
            print("4. Вставьте в MANUAL_COOKIES в начале файла")
            print("\n❌ Парсер не работает без cookies\n")
        
        self.session.headers.update(self.headers)
    
    def _validate_cookies(self) -> bool:
        required = ['cf_clearance', '__cf_bm', '_cfuvid']
        return all(MANUAL_COOKIES.get(k) for k in required)
    
    def set_manual_cookies(self, cookies: Dict[str, str]):
        global MANUAL_COOKIES
        MANUAL_COOKIES.update(cookies)
        self.session.cookies.update(cookies)
        print("✅ Cookies обновлены")
    
    def _init_session(self):
        if self._validate_cookies():
            self.session.cookies.update(MANUAL_COOKIES)
            print("✅ Cookies загружены")
        else:
            print("❌ Нет valid cookies")
    
    def get_sports(self) -> List[Dict]:
        url = f"{BASE_URL}/{self.partner_id}/live/sports"
        params = {'langId': self.lang_id, 'partnerId': self.partner_id, 'countryCode': self.country_code}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Получено видов спорта: {len(data) if isinstance(data, list) else 'N/A'}")
                return data if isinstance(data, list) else []
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return []
    
    def get_events(self, sport_id: int = 0) -> List[Dict]:
        if sport_id == 0:
            url = f"{BASE_URL}/{self.partner_id}/live/events"
        else:
            url = f"{BASE_URL}/{self.partner_id}/live/events?sportId={sport_id}"
        
        params = {'langId': self.lang_id, 'partnerId': self.partner_id, 'countryCode': self.country_code}
        
        try:
            response = self.session.get(url, params=params, timeout=10)
            if response.status_code == 200:
                data = response.json()
                events = data if isinstance(data, list) else data.get('events', [])
                print(f"✅ Получено событий: {len(events)}")
                return events
            else:
                print(f"❌ Ошибка {response.status_code}: {response.text[:200]}")
                return []
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return []
    
    def parse_event(self, event: Dict) -> Dict:
        return {
            'id': event.get('id'),
            'sport_id': event.get('sportId'),
            'league': event.get('leagueName', ''),
            'team1': event.get('homeTeam', event.get('team1', '')),
            'team2': event.get('awayTeam', event.get('team2', '')),
            'start_time': event.get('startDate', ''),
            'is_live': event.get('isLive', False),
            'score': event.get('score', ''),
            'markets': event.get('markets', [])
        }
    
    def get_all_events(self, only_live: bool = True) -> List[Dict]:
        sports = self.get_sports()
        all_events = []
        
        if not sports:
            events = self.get_events(0)
            for evt in events:
                parsed = self.parse_event(evt)
                if only_live and not parsed['is_live']:
                    continue
                all_events.append(parsed)
        else:
            for sport in sports[:5]:
                sport_id = sport.get('id', 0)
                events = self.get_events(sport_id)
                for evt in events:
                    parsed = self.parse_event(evt)
                    if only_live and not parsed['is_live']:
                        continue
                    all_events.append(parsed)
        
        return all_events
    
    def print_events(self, events: List[Dict], limit: int = 10):
        print(f"\n{'='*80}")
        print(f"СОБЫТИЯ (показано {min(len(events), limit)} из {len(events)})")
        print(f"{'='*80}")
        
        for i, evt in enumerate(events[:limit]):
            status = "🔴 LIVE" if evt['is_live'] else "⏳ Prematch"
            print(f"\n{i+1}. {status}")
            print(f"   {evt['league']}")
            print(f"   {evt['team1']} vs {evt['team2']}")
            if evt['score']:
                print(f"   Счёт: {evt['score']}")
            print(f"   Время: {evt['start_time']}")
            
            if evt['markets']:
                markets = evt['markets'][:3]
                odds_str = ', '.join([f"{m.get('name', 'N/A')}: {m.get('odds', 'N/A')}" for m in markets])
                print(f"   Коэфф: {odds_str}")
    
    def run(self, interval: int = 10, max_iterations: int = 3):
        print(f"\n🚀 Запуск парсера bet-m.ru")
        print(f"Интервал: {interval} сек, Итераций: {max_iterations}\n")
        
        self._init_session()
        
        if not self._validate_cookies():
            print("❌ ЗАПУСК НЕВОЗМОЖЕН: нет valid cookies")
            return
        
        for i in range(max_iterations):
            print(f"\n--- Итерация {i+1}/{max_iterations} ---")
            start_time = time.time()
            
            events = self.get_all_events(only_live=True)
            self.print_events(events, limit=5)
            
            elapsed = time.time() - start_time
            print(f"\n⏱ Затрачено времени: {elapsed:.2f} сек")
            
            if i < max_iterations - 1:
                print(f"😴 Сон {interval} секунд...")
                time.sleep(interval)
        
        print("\n✅ Парсинг завершён")


if __name__ == "__main__":
    parser = BetMParser()
    parser.run(interval=10, max_iterations=2)
