"""
Парсер для букмекерской конторы Fonbet (fon.bet)
Использует API платформы BetConstruct (аналогично 24bet).
API: https://line-lb54-w.bk6bba-resources.com/ma/events/list
"""

import requests
import time
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class FonbetParser:
    def __init__(self):
        # Основные домены API (используем несколько для отказоустойчивости)
        self.base_urls = [
            "https://line-lb54-w.bk6bba-resources.com",
            "https://line-lb52-w.bk6bba-resources.ru",
            "https://line-lb61-w.bk6bba-resources.com"
        ]
        self.current_url_index = 0
        
        # Параметры запроса
        self.params = {
            'lang': 'ru',
            'version': '0',
            'scopeMarket': '1600'
        }
        
        # Заголовки
        self.headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate, br, zstd',
            'Accept-Language': 'ru,en;q=0.9',
            'Origin': 'https://fon.bet',
            'Referer': 'https://fon.bet/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3", "Yowser";v="2.5"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site'
        }
        
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        self.packet_version = '0'
        self.events_cache = {}
        
    def _get_current_url(self) -> str:
        return self.base_urls[self.current_url_index]
    
    def _rotate_url(self):
        self.current_url_index = (self.current_url_index + 1) % len(self.base_urls)

    def fetch_events(self) -> Optional[Dict]:
        """Получение списка событий с обновлением версии"""
        self.params['version'] = self.packet_version
        url = f"{self._get_current_url()}/ma/events/list"
        
        try:
            response = self.session.get(url, params=self.params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'packetVersion' in data:
                    self.packet_version = str(data['packetVersion'])
                return data
            elif response.status_code in [403, 429]:
                print(f"[Fonbet] Блокировка ({response.status_code}), смена URL...")
                self._rotate_url()
                time.sleep(2)
                return self.fetch_events()
            else:
                print(f"[Fonbet] Статус ответа: {response.status_code}")
                return None
                
        except requests.exceptions.RequestException as e:
            print(f"[Fonbet] Ошибка запроса: {e}")
            self._rotate_url()
            return None
        except json.JSONDecodeError as e:
            print(f"[Fonbet] Ошибка JSON: {e}")
            return None

    def parse_sports(self, data: Dict) -> List[Dict]:
        """Извлечение видов спорта"""
        sports = []
        if 'sports' in data:
            for item in data['sports']:
                if item.get('kind') == 'sport':
                    sports.append({
                        'id': item.get('id'),
                        'name': item.get('name'),
                        'order': item.get('sortOrder', 0)
                    })
        return sorted(sports, key=lambda x: x['order'])

    def parse_events(self, data: Dict, only_live: bool = False) -> List[Dict]:
        """Извлечение событий (матчей)"""
        events = []
        if 'events' not in data:
            return events
            
        for event in data['events']:
            if event.get('level') != 1:
                continue
                
            is_live = event.get('place') == 'live'
            if only_live and not is_live:
                continue
            
            score = "-"
            timer = ""
            if is_live and 'eventMiscs' in data:
                for misc in data['eventMiscs']:
                    if misc.get('eventId') == event.get('id'):
                        s1 = misc.get('score1', 0)
                        s2 = misc.get('score2', 0)
                        score = f"{s1}:{s2}"
                        t_sec = misc.get('timerSeconds', 0)
                        if t_sec:
                            m, s = divmod(int(t_sec), 60)
                            timer = f"{m:02d}:{s:02d}"
                        break
            
            event_info = {
                'id': event.get('id'),
                'sport_id': event.get('sportId'),
                'team1': event.get('team1', ''),
                'team2': event.get('team2', ''),
                'start_time': datetime.fromtimestamp(event.get('startTime', 0)).strftime('%Y-%m-%d %H:%M') if event.get('startTime') else 'TBA',
                'is_live': is_live,
                'score': score,
                'timer': timer,
                'markets_count': len(event.get('customFactors', []))
            }
            events.append(event_info)
            
        return events

    def run(self, interval: int = 5, max_iterations: int = 0):
        """Запуск цикла парсинга"""
        print(f"[Fonbet] Запуск парсера...")
        iteration = 0
        
        while True:
            iteration += 1
            if max_iterations > 0 and iteration > max_iterations:
                break
                
            data = self.fetch_events()
            if data:
                sports = self.parse_sports(data)
                events = self.parse_events(data)
                live_events = self.parse_events(data, only_live=True)
                
                print(f"\n--- Fonbet Update (Ver: {self.packet_version}) ---")
                print(f"Видов спорта: {len(sports)}")
                print(f"Всего событий: {len(events)}")
                print(f"Live событий: {len(live_events)}")
                
                if live_events:
                    print("\n🔴 LIVE:")
                    for ev in live_events[:5]:
                        print(f"  {ev['timer']} | {ev['team1']} vs {ev['team2']} ({ev['score']})")
                        
            else:
                print("[Fonbet] Не удалось получить данные")
                
            time.sleep(interval)

if __name__ == "__main__":
    parser = FonbetParser()
    parser.run(interval=5, max_iterations=3)
