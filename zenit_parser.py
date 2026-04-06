#!/usr/bin/env python3
"""
Парсер для Zenit.win
API: https://zenit.win/ajax/line/left_menu/get
"""

import requests
import time
from typing import List, Dict, Any, Optional

class ZenitParser:
    def __init__(self):
        self.base_url = "https://zenit.win"
        self.session = requests.Session()
        self.events: List[Dict[str, Any]] = []
        
        # Заголовки из анализа трафика
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ru,en;q=0.9',
            'Connection': 'keep-alive',
            'Referer': 'https://zenit.win/',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36',
            'sec-ch-ua': '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3", "Yowser";v="2.5"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
        }
        
        # Cookie и параметры
        self.cookies = {
            'lang': '1',
            'timezone': '3',
            'user_logged_in': '0'
        }
        
        # Генерируем простой imprint hash (можно улучшить)
        import hashlib
        self.imprint_hash = hashlib.md5(f"zenit_{time.time()}".encode()).hexdigest()
        
        self.headers['imprinthash'] = self.imprint_hash
        self.headers['frontversion'] = '1.72.1'
        
        self.session.headers.update(self.headers)
        self.session.cookies.update(self.cookies)
    
    def fetch_data(self, sport_id: Optional[int] = None) -> bool:
        """Получить данные о событиях"""
        try:
            url = f"{self.base_url}/ajax/line/left_menu/get"
            params = {
                'lang_id': '1',
                'sort_mode': '2',  # 2 = по времени
                'tournaments_mode': '1'
            }
            
            if sport_id:
                params['sport_id'] = str(sport_id)
            
            response = self.session.get(url, params=params, timeout=15)
            response.raise_for_status()
            
            data = response.json()
            
            # Обработка ответа
            if isinstance(data, dict):
                if 'data' in data:
                    self._parse_events(data['data'])
                elif 'events' in data:
                    self._parse_events(data['events'])
                else:
                    # Пробуем найти события в структуре
                    self._recursive_search(data)
            elif isinstance(data, list):
                self._parse_events(data)
            
            return True
            
        except Exception as e:
            print(f"Ошибка при получении данных Zenit: {e}")
            return False
    
    def _recursive_search(self, data: Any, depth: int = 0) -> None:
        """Рекурсивный поиск событий в структуре"""
        if depth > 5:
            return
            
        if isinstance(data, dict):
            # Проверяем, похоже ли это на событие
            if any(key in data for key in ['event_id', 'id', 'team1', 'team2', 'home', 'away', 'coeffs', 'odds']):
                self._parse_single_event(data)
            
            # Ищем вложенные структуры
            for key, value in data.items():
                if key in ['events', 'matches', 'games', 'data', 'items', 'list']:
                    self._parse_events(value)
                elif isinstance(value, (dict, list)):
                    self._recursive_search(value, depth + 1)
                    
        elif isinstance(data, list):
            for item in data:
                self._recursive_search(item, depth + 1)
    
    def _parse_events(self, data: Any) -> None:
        """Парсинг списка событий"""
        if not isinstance(data, list):
            return
            
        for item in data:
            if isinstance(item, dict):
                self._parse_single_event(item)
            elif isinstance(item, list):
                self._parse_events(item)
    
    def _parse_single_event(self, event_data: Dict[str, Any]) -> None:
        """Парсинг одного события"""
        try:
            # Извлекаем основные поля
            event_id = event_data.get('event_id') or event_data.get('id') or event_data.get('game_id')
            if not event_id:
                return
            
            # Проверяем, нет ли уже такого события
            if any(e.get('id') == event_id for e in self.events):
                return
            
            # Команды
            team1 = event_data.get('team1') or event_data.get('home') or event_data.get('home_team') or ''
            team2 = event_data.get('team2') or event_data.get('away') or event_data.get('away_team') or ''
            
            # Время
            start_time = event_data.get('start_time') or event_data.get('time') or event_data.get('date')
            
            # Тип события (live/prematch)
            is_live = event_data.get('is_live') or event_data.get('live') or event_data.get('in_play') or False
            place = 'live' if is_live else 'line'
            
            # Коэффициенты
            odds = {}
            if 'coeffs' in event_data:
                odds = event_data['coeffs']
            elif 'odds' in event_data:
                odds = event_data['odds']
            elif 'markets' in event_data:
                # Обрабатываем рынки
                for market in event_data.get('markets', []):
                    market_name = market.get('name', 'unknown')
                    odds[market_name] = market.get('outcomes', [])
            
            event = {
                'id': event_id,
                'sport': event_data.get('sport_name') or event_data.get('sport') or 'Unknown',
                'league': event_data.get('league_name') or event_data.get('tournament') or event_data.get('league') or '',
                'team1': team1,
                'team2': team2,
                'start_time': start_time,
                'place': place,
                'is_live': is_live,
                'score': event_data.get('score') or event_data.get('current_score'),
                'odds': odds,
                'raw': event_data
            }
            
            self.events.append(event)
            
        except Exception as e:
            pass  # Игнорируем ошибки парсинга отдельных событий
    
    def get_all_events(self, only_live: bool = False, only_prematch: bool = False) -> List[Dict[str, Any]]:
        """Получить все события с фильтрацией"""
        if only_live:
            return [e for e in self.events if e.get('place') == 'live']
        elif only_prematch:
            return [e for e in self.events if e.get('place') == 'line']
        return self.events
    
    def get_statistics(self) -> Dict[str, int]:
        """Получить статистику"""
        total = len(self.events)
        live = len([e for e in self.events if e.get('place') == 'live'])
        prematch = total - live
        return {'total': total, 'live': live, 'prematch': prematch}


def main():
    print("Запуск парсера Zenit.win...")
    parser = ZenitParser()
    
    print("Получение данных...")
    success = parser.fetch_data()
    
    if success:
        stats = parser.get_statistics()
        print(f"\n{'='*50}")
        print(f"Zenit.win - Результаты:")
        print(f"{'='*50}")
        print(f"Всего событий: {stats['total']}")
        print(f"Live: {stats['live']}")
        print(f"Prematch: {stats['prematch']}")
        print(f"{'='*50}")
        
        # Показать несколько примеров
        events = parser.get_all_events()
        if events:
            print("\nПримеры событий:")
            for i, event in enumerate(events[:5]):
                print(f"{i+1}. {event['team1']} vs {event['team2']} ({event['place']})")
    else:
        print("Не удалось получить данные")


if __name__ == "__main__":
    main()
