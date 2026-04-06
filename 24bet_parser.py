#!/usr/bin/env python3
"""
Парсер спортивных событий и коэффициентов 24bet.ru
Использует API line51.tf39be-resources.com
"""

import requests
import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any

class TwentyFourBetParser:
    def __init__(self):
        self.base_url = "https://line51.tf39be-resources.com"
        self.version = 0
        self.session = requests.Session()
        
        # Заголовки для имитации браузера
        self.headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "ru,en;q=0.9",
            "Connection": "keep-alive",
            "Origin": "https://24bet.ru",
            "Referer": "https://24bet.ru/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36",
            "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144", "YaBrowser";v="26.3", "Yowser";v="2.5"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "cross-site"
        }
        
        # Кэши данных
        self.events_data: Dict[int, Dict] = {}  # eventId -> event info
        self.scores_data: Dict[int, Dict] = {}  # eventId -> score info
        self.live_infos: Dict[int, Dict] = {}  # eventId -> live stats
        self.factors_data: Dict[int, List[Dict]] = {}  # eventId -> factors list
        
        # Коды факторов (расшифровка)
        self.factor_names = {
            910: "Победа 1",
            911: "Ничья",
            912: "Победа 2",
            921: "ТМ",
            922: "ТБ",
            923: "ТМ",
            924: "ТБ",
            925: "ТМ",
            927: "ТМ с форой",
            928: "ТБ с форой",
            930: "Фора 1",
            931: "Фора 2",
            974: "Тотал голов М",
            976: "Тотал голов Б",
        }

    def get_events_list(self) -> Optional[Dict]:
        """Запросить список событий с сервера"""
        params = {
            "lang": "ru",
            "version": self.version,
            "scopeMarket": "3000"
        }
        
        url = f"{self.base_url}/events/list"
        
        try:
            response = self.session.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Ошибка запроса: {e}")
            return None

    def process_response(self, data: Dict) -> None:
        """Обработать ответ от API и обновить кэш"""
        
        # Обновляем версию
        new_version = data.get("packetVersion", 0)
        if new_version > self.version:
            self.version = new_version
            print(f"Версия обновлена: {self.version}")
        
        # Обрабатываем события
        events = data.get("events", [])
        for event in events:
            event_id = event.get("id")
            if event_id:
                # level=1 - основные события
                if event.get("level") == 1:
                    self.events_data[event_id] = event
                elif event.get("parentId"):
                    # Дочерние события (таймы, периоды) - тоже сохраняем
                    self.events_data[event_id] = event
        
        # Обрабатываем счета (eventMiscs)
        miscs = data.get("eventMiscs", [])
        for misc in miscs:
            event_id = misc.get("id")
            if event_id:
                self.scores_data[event_id] = misc
        
        # Обрабатываем детальную live-статистику
        live_infos = data.get("liveEventInfos", [])
        for info in live_infos:
            event_id = info.get("eventId")
            if event_id:
                self.live_infos[event_id] = info
        
        # Обрабатываем коэффициенты (customFactors)
        custom_factors = data.get("customFactors", [])
        for cf in custom_factors:
            event_id = cf.get("e")
            if event_id:
                self.factors_data[event_id] = cf.get("factors", [])

    def get_event_summary(self, event_id: int) -> Optional[Dict]:
        """Получить сводку по событию с коэффициентами и счетом"""
        event = self.events_data.get(event_id)
        if not event:
            return None
        
        summary = {
            "id": event_id,
            "sport_id": event.get("sportId"),
            "team1": event.get("team1", ""),
            "team2": event.get("team2", ""),
            "start_time": event.get("startTime"),
            "start_time_str": datetime.fromtimestamp(event.get("startTime", 0)).strftime("%Y-%m-%d %H:%M") if event.get("startTime") else "",
            "place": event.get("place", "line"),
            "status": "live" if event.get("place") == "live" else "prematch",
        }
        
        # Добавляем счет если есть
        score = self.scores_data.get(event_id)
        if score:
            summary["score"] = {
                "team1": score.get("score1", 0),
                "team2": score.get("score2", 0),
                "timer": self._format_timer(score),
            }
        
        # Добавляем основные коэффициенты
        factors = self.factors_data.get(event_id, [])
        if factors:
            summary["odds"] = self._parse_factors(factors)
        
        return summary

    def _format_timer(self, score: Dict) -> str:
        """Форматировать таймер матча"""
        timer_sec = score.get("timerSeconds", 0)
        direction = score.get("timerDirection", 1)
        
        minutes = timer_sec // 60
        seconds = timer_sec % 60
        
        if direction == 0:
            return f"-{minutes}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _parse_factors(self, factors: List[Dict]) -> Dict[str, Any]:
        """Распарсить коэффициенты в удобном формате"""
        odds = {
            "1X2": {},
            "totals": [],
            "handicaps": []
        }
        
        for f in factors:
            factor_code = f.get("f")
            value = f.get("v")
            param = f.get("p")  # фора или значение тотала
            param_text = f.get("pt")  # текстовое описание
            
            if factor_code in [910, 911, 912]:
                if factor_code == 910:
                    odds["1X2"]["1"] = value
                elif factor_code == 911:
                    odds["1X2"]["X"] = value
                elif factor_code == 912:
                    odds["1X2"]["2"] = value
            
            elif factor_code in [930, 931]:
                handicap_type = "1" if factor_code == 930 else "2"
                odds["handicaps"].append({
                    "type": handicap_type,
                    "value": param_text or param,
                    "odd": value
                })
            
            elif factor_code in [927, 928]:
                total_type = "under" if factor_code == 927 else "over"
                odds["totals"].append({
                    "type": total_type,
                    "value": param_text or param,
                    "odd": value
                })
            
            elif factor_code in [921, 922, 923, 924, 925]:
                total_type = "under" if factor_code in [921, 923, 925] else "over"
                odds["totals"].append({
                    "type": total_type,
                    "odd": value
                })
        
        return odds

    def get_all_events(self, only_live: bool = False, only_with_odds: bool = True) -> List[Dict]:
        """Получить все события с фильтрацией"""
        result = []
        
        for event_id in self.events_data:
            event = self.events_data[event_id]
            
            # Фильтр по live/prematch
            if only_live and event.get("place") != "live":
                continue
            
            # Пропускаем события без названия команд
            team1 = event.get("team1", "")
            team2 = event.get("team2", "")
            if not team1 or not team2:
                continue
            
            summary = self.get_event_summary(event_id)
            if not summary:
                continue
            
            # Фильтр по наличию коэффициентов
            if only_with_odds and not summary.get("odds"):
                continue
            
            result.append(summary)
        
        # Сортировка: сначала live, потом по времени
        result.sort(key=lambda x: (0 if x["status"] == "live" else 1, x.get("start_time", 0)))
        
        return result

    def run(self, interval: int = 5, max_iterations: int = 10) -> None:
        """Запустить цикл обновления данных"""
        print("Запуск парсера 24bet.ru...")
        print(f"Интервал обновления: {interval} сек.")
        print(f"Максимум итераций: {max_iterations}")
        print("-" * 50)
        
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Итерация {iteration}")
            
            # Запрос данных
            print("Запрос списка событий...")
            data = self.get_events_list()
            
            if not data:
                print("Не удалось получить данные, повтор через 5 сек...")
                time.sleep(5)
                continue
            
            # Обработка
            print(f"Получен ответ, версия пакета: {data.get('packetVersion')}")
            self.process_response(data)
            
            # Вывод краткой статистики
            live_events = [e for e in self.events_data.values() if e.get("place") == "live"]
            prematch_events = [e for e in self.events_data.values() if e.get("place") == "line"]
            
            print(f"Всего событий в кэше: {len(self.events_data)}")
            print(f"  Live: {len(live_events)}")
            print(f"  Prematch: {len(prematch_events)}")
            print(f"События с коэффициентами: {len(self.factors_data)}")
            print(f"События со счетом: {len(self.scores_data)}")
            
            # Показать несколько live-событий с коэффициентами
            live_summaries = self.get_all_events(only_live=True, only_with_odds=True)[:3]
            if live_summaries:
                print("\n--- LIVE матчи (топ-3) ---")
                for evt in live_summaries:
                    score = evt.get("score", {})
                    score_str = f"{score.get('team1', 0)}:{score.get('team2', 0)} ({score.get('timer', '?')})" if score else "-"
                    odds = evt.get("odds", {}).get("1X2", {})
                    odds_str = f"1:{odds.get('1', '-')}/X:{odds.get('X', '-')}/2:{odds.get('2', '-')}." if odds else "нет 1X2"
                    
                    print(f"  {evt['team1']} vs {evt['team2']}")
                    print(f"    Счет: {score_str}")
                    print(f"    Коэф: {odds_str}")
            
            if iteration < max_iterations:
                time.sleep(interval)
        
        print("\n" + "=" * 50)
        print("Цикл завершен. Данные доступны в get_all_events()")


if __name__ == "__main__":
    parser = TwentyFourBetParser()
    parser.run(interval=5, max_iterations=3)
    
    # После запуска можно получить все события
    # all_events = parser.get_all_events()
    # live_events = parser.get_all_events(only_live=True)
