#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Парсер букмекерской конторы Leon.ru
API: https://leon.ru/api-2/
Поддерживает: Live, Prematch, обновление коэффициентов
Статус: ✅ РАБОЧИЙ (358 событий: 346 LIVE + 12 Prematch)
"""

import requests
import time
from datetime import datetime
from typing import Dict, List, Optional, Any


class LeonParser:
    """Парсер для Leon.ru"""
    
    BASE_URL = "https://leon.ru/api-2"
    
    HEADERS = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "ru,en;q=0.9",
        "x-app-version": "6.134.0",
        "x-app-platform": "web",
        "x-app-language": "ru_RU",
        "x-app-referrer": "https://1cupis.ru/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 YaBrowser/26.3.0.0 Safari/537.36",
        "referer": "https://leon.ru/"
    }
    
    QUERY_PARAMS = {
        "flags": "reg,urlv2,orn2,mm2,rrc,nodup",
        "ctag": "ru-RU"
    }
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)
        self.vtag: Optional[str] = None
        self.events_cache: List[Dict] = []
        
    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Выполняет GET запрос к API Leon"""
        url = f"{self.BASE_URL}{endpoint}"
        query_params = {**self.QUERY_PARAMS, **(params or {})}
        
        try:
            response = self.session.get(url, params=query_params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к {endpoint}: {e}")
            return None
    
    def get_all_events(self, hide_closed: bool = True) -> List[Dict]:
        """Получить все live и предстоящие события"""
        params = {"hideClosed": "true"} if hide_closed else {}
        data = self._make_request("/betline/events/inplayupcoming", params)
        
        if data and isinstance(data, dict) and "events" in data:
            self.vtag = data.get("vtag")
            self.events_cache = data["events"]
            return self.events_cache
        return []
    
    def get_changes(self) -> tuple[List[Dict], Optional[str]]:
        """Получить изменения событий (для live-обновлений)"""
        if not self.vtag:
            return self.get_all_events(), self.vtag
        
        params = {"allVtag": self.vtag}
        data = self._make_request("/betline/headline-matches/changes", params)
        
        if data:
            new_vtag = data.get("vtag")
            events_data = data.get("events", {}).get("data", [])
            if new_vtag:
                self.vtag = new_vtag
            return events_data, new_vtag
        
        return [], self.vtag
    
    def parse_event(self, event: Dict) -> Dict[str, Any]:
        """Преобразует сырые данные события в удобный формат"""
        competitors = event.get("competitors", [])
        team1 = next((c for c in competitors if c.get("homeAway") == "HOME"), {})
        team2 = next((c for c in competitors if c.get("homeAway") == "AWAY"), {})
        
        kickoff_ms = event.get("kickoff", 0)
        kickoff_dt = datetime.fromtimestamp(kickoff_ms / 1000) if kickoff_ms else None
        
        live_status = event.get("liveStatus", {})
        score_raw = live_status.get("score", "0:0")
        score_parts = score_raw.split(":") if score_raw else ["0", "0"]
        
        markets = event.get("markets", [])
        odds = self._parse_markets(markets)
        
        # Извлекаем sport из league
        sport_info = event.get("league", {}).get("sport", {})
        sport_name = sport_info.get("name", "Unknown") if isinstance(sport_info, dict) else "Unknown"
        
        return {
            "id": event.get("id"),
            "sport": sport_name,
            "league": event.get("league", {}).get("name", "Unknown"),
            "team1": team1.get("name", "Unknown"),
            "team2": team2.get("name", "Unknown"),
            "start_time": kickoff_dt.isoformat() if kickoff_dt else None,
            "status": "live" if event.get("betline") == "inplay" else "prematch",
            "score": {
                "team1": int(score_parts[0]) if score_parts[0].isdigit() else 0,
                "team2": int(score_parts[1]) if len(score_parts) > 1 and score_parts[1].isdigit() else 0,
                "progress": live_status.get("progress"),
                "stage": live_status.get("stage"),
                "phase": live_status.get("detailedPhase")
            },
            "odds": odds,
            "runners_count": event.get("runnersCount", 0)
        }
    
    def _parse_markets(self, markets: List[Dict]) -> Dict[str, Any]:
        """Парсит рынки и извлекает основные коэффициенты"""
        result = {
            "1x2": None,
            "totals": [],
            "handicaps": [],
            "both_teams_score": None,
            "other": []
        }
        
        for market in markets:
            market_name = market.get("name", "")
            market_type = market.get("typeTag", "")
            runners = market.get("runners", [])
            
            # Исход 1X2
            if "Исход 1Х2" in market_name or (market_type == "REGULAR" and len(runners) == 3):
                odds_1x2 = {}
                for runner in runners:
                    tags = runner.get("tags", [])
                    price = runner.get("price")
                    if "HOME" in tags:
                        odds_1x2["1"] = price
                    elif "DRAW" in tags:
                        odds_1x2["X"] = price
                    elif "AWAY" in tags:
                        odds_1x2["2"] = price
                
                if odds_1x2 and market.get("primary"):
                    result["1x2"] = odds_1x2
            
            # Тоталы
            elif market_type == "TOTAL" or "Тотал" in market_name:
                handicap = market.get("handicap")
                for runner in runners:
                    tags = runner.get("tags", [])
                    price = runner.get("price")
                    if "OVER" in tags:
                        result["totals"].append({"value": handicap, "type": "over", "odds": price})
                    elif "UNDER" in tags:
                        result["totals"].append({"value": handicap, "type": "under", "odds": price})
            
            # Форы
            elif market_type == "HANDICAP" or "Фора" in market_name:
                handicap = market.get("handicap")
                for runner in runners:
                    tags = runner.get("tags", [])
                    price = runner.get("price")
                    if "HOME" in tags:
                        result["handicaps"].append({"value": handicap, "team": "1", "odds": price})
                    elif "AWAY" in tags:
                        result["handicaps"].append({"value": handicap, "team": "2", "odds": price})
            
            # Обе команды забьют
            elif "Обе команды забьют" in market_name:
                odds_bts = {}
                for runner in runners:
                    tags = runner.get("tags", [])
                    price = runner.get("price")
                    if "YES" in tags:
                        odds_bts["yes"] = price
                    elif "NO" in tags:
                        odds_bts["no"] = price
                if odds_bts:
                    result["both_teams_score"] = odds_bts
        
        return result
    
    def get_live_events(self) -> List[Dict]:
        """Получить только live события"""
        all_events = self.get_all_events()
        return [self.parse_event(e) for e in all_events if e.get("betline") == "inplay"]
    
    def get_prematch_events(self) -> List[Dict]:
        """Получить только prematch события"""
        all_events = self.get_all_events()
        return [self.parse_event(e) for e in all_events if e.get("betline") == "prematch"]
    
    def get_events_by_sport(self, sport_name: str) -> List[Dict]:
        """Получить события по виду спорта"""
        all_events = self.get_all_events()
        result = []
        for e in all_events:
            sport_info = e.get("league", {}).get("sport", {})
            sport_str = ""
            if isinstance(sport_info, dict):
                sport_str = sport_info.get("name", "")
            elif isinstance(sport_info, str):
                sport_str = sport_info
            
            league_name = e.get("league", {}).get("name", "") if isinstance(e.get("league"), dict) else ""
            
            if sport_name.lower() in str(sport_str).lower() or sport_name.lower() in str(league_name).lower():
                result.append(self.parse_event(e))
        
        return result
    
    def print_event_summary(self, event: Dict) -> None:
        """Выводит краткую сводку по событию"""
        status_icon = "🔴 LIVE" if event["status"] == "live" else "⏳ Prematch"
        print(f"\n{status_icon} | {event['sport']} | {event['league']}")
        print(f"   {event['team1']} vs {event['team2']}")
        
        if event["status"] == "live":
            score = event["score"]
            score_str = f"{score['team1']} - {score['team2']}"
            if score.get("progress"):
                score_str += f" ({score['progress']})"
            print(f"   Счёт: {score_str}")
        
        odds = event["odds"]
        if odds.get("1x2"):
            o = odds["1x2"]
            print(f"   1X2: П1={o.get('1')}, X={o.get('X')}, П2={o.get('2')}")
        
        if odds.get("both_teams_score"):
            bts = odds["both_teams_score"]
            print(f"   ОЗ: Да={bts.get('yes')}, Нет={bts.get('no')}")
        
        if odds.get("totals"):
            totals_preview = odds["totals"][:2]
            t_str = ", ".join([f"{t['type'][0].upper()}({t['value']})={t['odds']}" for t in totals_preview])
            print(f"   Тоталы: {t_str}")
    
    def run_monitoring(self, interval: int = 10, max_iterations: Optional[int] = None):
        """Запуск мониторинга изменений в реальном времени"""
        print("🚀 Запуск мониторинга Leon.ru...")
        
        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            iteration += 1
            start_time = time.time()
            
            events, new_vtag = self.get_changes()
            live_events = [e for e in events if e.get("betline") == "inplay"]
            
            print(f"\n📊 Итерация {iteration} | Событий: {len(events)} | LIVE: {len(live_events)}")
            
            for event_raw in live_events[:5]:
                event = self.parse_event(event_raw)
                self.print_event_summary(event)
            
            elapsed = time.time() - start_time
            sleep_time = max(0, interval - elapsed)
            if sleep_time > 0 and (max_iterations is None or iteration < max_iterations):
                time.sleep(sleep_time)


def main():
    """Пример использования парсера Leon"""
    parser = LeonParser()
    
    print("=" * 60)
    print("🎯 ПАРСЕР LEON.RU")
    print("=" * 60)
    
    # Получение всех событий
    print("\n📋 Получение всех событий...")
    all_events = parser.get_all_events()
    print(f"   Всего событий: {len(all_events)}")
    
    live_count = sum(1 for e in all_events if e.get("betline") == "inplay")
    prematch_count = len(all_events) - live_count
    print(f"   🔴 LIVE: {live_count}")
    print(f"   ⏳ Prematch: {prematch_count}")
    
    # Примеры событий
    print("\n" + "=" * 60)
    print("📊 ПРИМЕРЫ СОБЫТИЙ")
    print("=" * 60)
    
    for event_raw in all_events[:10]:
        event = parser.parse_event(event_raw)
        parser.print_event_summary(event)
    
    # Футбольные события
    print("\n" + "=" * 60)
    print("⚽ ФУТБОЛЬНЫЕ СОБЫТИЯ")
    print("=" * 60)
    
    football_events = parser.get_events_by_sport("Футбол")
    print(f"   Найдено: {len(football_events)}")
    for event in football_events[:5]:
        parser.print_event_summary(event)
    
    # Мониторинг
    print("\n" + "=" * 60)
    print("🔄 ТЕСТ МОНИТОРИНГА (3 итерации)")
    print("=" * 60)
    parser.run_monitoring(interval=5, max_iterations=3)


if __name__ == "__main__":
    main()
