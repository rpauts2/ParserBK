"""
Парсер для Olimp (olimp.bet)
API: https://api.olimp.bet
Использует публичное API для получения событий и коэффициентов
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Any


class OlimpParser:
    def __init__(self):
        self.base_url = "https://api.olimp.bet"
        self.session = requests.Session()
        self.session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.7,en;q=0.3',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.olimp.bet/',
            'Origin': 'https://www.olimp.bet',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'cross-site',
        })
        self.events_cache: Dict[int, Dict] = {}
        self.last_update = None
        
    def get_sports(self) -> List[Dict]:
        """Получить список видов спорта"""
        try:
            url = f"{self.base_url}/sports"
            response = self.session.get(url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                return data if isinstance(data, list) else data.get('data', [])
        except Exception as e:
            print(f"[Olimp] Ошибка получения sports: {e}")
        return []
    
    def get_events(self, sport_id: Optional[int] = None, live: bool = False) -> List[Dict]:
        """
        Получить события
        :param sport_id: ID вида спорта (None = все)
        :param live: True = live события, False = прематч
        """
        try:
            url = f"{self.base_url}/events"
            params = {'lang': 'ru'}
            
            if live:
                params['live'] = 'true'
            if sport_id:
                params['sport_id'] = sport_id
                
            response = self.session.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json()
                events = data if isinstance(data, list) else data.get('data', [])
                
                for event in events:
                    event_id = event.get('id')
                    if event_id:
                        self.events_cache[event_id] = event
                        
                self.last_update = datetime.now()
                return events
        except Exception as e:
            print(f"[Olimp] Ошибка получения events: {e}")
        return []
    
    def get_live_events(self) -> List[Dict]:
        """Получить только live события"""
        return self.get_events(live=True)
    
    def get_prematch_events(self) -> List[Dict]:
        """Получить только прематч события"""
        return self.get_events(live=False)
    
    def parse_event_summary(self, event: Dict) -> Dict:
        """Преобразовать событие в удобный формат"""
        home_team = event.get('home_team', '') or (event.get('home', {}).get('name', '') if isinstance(event.get('home'), dict) else '')
        away_team = event.get('away_team', '') or (event.get('away', {}).get('name', '') if isinstance(event.get('away'), dict) else '')
        
        return {
            'id': event.get('id'),
            'sport_id': event.get('sport_id'),
            'league': event.get('league_name', '') or (event.get('league', {}).get('name', '') if isinstance(event.get('league'), dict) else ''),
            'home_team': home_team,
            'away_team': away_team,
            'start_time': event.get('start_time') or event.get('starts_at'),
            'is_live': event.get('is_live', False) or event.get('live', False),
            'score': event.get('score', ''),
        }
    
    def run(self, interval: int = 10, max_iterations: int = 0):
        """Запустить цикл обновления данных"""
        iteration = 0
        print(f"[Olimp] Запуск парсера (интервал: {interval}с)")
        
        try:
            while max_iterations == 0 or iteration < max_iterations:
                start_time = time.time()
                
                live_events = self.get_live_events()
                prematch_events = self.get_prematch_events()
                
                print(f"\n[Olimp] Итерация {iteration + 1}")
                print(f"  Live событий: {len(live_events)}")
                print(f"  Prematch событий: {len(prematch_events)}")
                print(f"  Всего в кэше: {len(self.events_cache)}")
                
                if live_events:
                    print("\n  Примеры Live:")
                    for event in live_events[:3]:
                        summary = self.parse_event_summary(event)
                        print(f"    - {summary['home_team']} vs {summary['away_team']}")
                
                iteration += 1
                
                if max_iterations == 0 or iteration < max_iterations:
                    elapsed = time.time() - start_time
                    sleep_time = max(0, interval - elapsed)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                        
        except KeyboardInterrupt:
            print("\n[Olimp] Остановка парсера")
        except Exception as e:
            print(f"[Olimp] Критическая ошибка: {e}")


if __name__ == "__main__":
    parser = OlimpParser()
    
    print("=== Тест Olimp Parser ===\n")
    
    sports = parser.get_sports()
    print(f"Виды спорта: {len(sports)}")
    
    live = parser.get_live_events()
    prematch = parser.get_prematch_events()
    
    print(f"\nLive событий: {len(live)}")
    print(f"Prematch событий: {len(prematch)}")
    
    if live:
        print("\nПримеры Live событий:")
        for event in live[:3]:
            summary = parser.parse_event_summary(event)
            print(f"  {summary['home_team']} vs {summary['away_team']}")
    
    print("\n=== Запуск цикла (3 итерации) ===")
    parser.run(interval=5, max_iterations=3)
