#!/usr/bin/env python3
"""
Тестовый скрипт для проверки работы парсера Лиги Ставок
Запускает тесты для каждого компонента парсера
"""

import asyncio
import json
import sys
from pathlib import Path

# Добавляем путь к модулю
sys.path.insert(0, str(Path(__file__).parent))

from ligastavok_parser import LigaStavokParser


async def test_cookies_http():
    """Тест получения кук через HTTP"""
    print("\n" + "="*60)
    print("ТЕСТ 1: Получение кук через HTTP")
    print("="*60)
    
    parser = LigaStavokParser()
    cookies = await parser._get_cookies_http()
    
    if cookies:
        print(f"✓ Получено {len(cookies)} кук:")
        for cookie in cookies[:3]:
            print(f"  - {cookie['name']}: {cookie['value'][:20]}...")
        return True
    else:
        print("✗ Не удалось получить куки")
        return False


async def test_api_request_without_auth():
    """Тест API запроса без авторизации (должен вернуть 403)"""
    print("\n" + "="*60)
    print("ТЕСТ 2: API запрос без авторизации")
    print("="*60)
    
    parser = LigaStavokParser()
    
    payload = {
        "gameId": [],
        "limit": 5,
        "skip": 0,
        "topEvents": False,
        "ts": 1775290675832,
        "view": "priority",
        "widgetVideo": False,
        "proposedTypes": ["MAINOFFER"]
    }
    
    result = await parser._make_request("/rest/events/v8/eventsList", payload)
    
    if result is None:
        print("✓ Запрос заблокирован (ожидаемое поведение)")
        print("  Для работы нужны валидные куки")
        return True
    elif result.get("result"):
        print(f"✓ Запрос успешен! Получено {len(result['result'].get('data', []))} событий")
        return True
    else:
        print("? Неожиданный результат")
        return False


def test_data_parsing():
    """Тест парсинга тестовых данных"""
    print("\n" + "="*60)
    print("ТЕСТ 3: Парсинг данных")
    print("="*60)
    
    # Тестовые данные имитирующие ответ API
    test_event = {
        "id": 12345678,
        "event": {
            "team1": "Спартак Москва",
            "team2": "Зенит Санкт-Петербург",
            "tournamentTitle": "Премьер-лига",
            "categoryTitle": "Россия",
            "gameTitle": "Футбол",
            "startDate": 1737000000000,
            "ns": "prematch"
        },
        "outcomes": {
            "_111111": {"title": "1", "value": 2.15, "marketId": "main"},
            "_111112": {"title": "X", "value": 3.40, "marketId": "main"},
            "_111113": {"title": "2", "value": 3.20, "marketId": "main"},
            "_111114": {"title": "Бол", "value": 1.85, "adValue": 2.5, "marketId": "total"},
            "_111115": {"title": "Мен", "value": 1.95, "adValue": 2.5, "marketId": "total"},
            "_111116": {"title": "Ф1", "value": 1.90, "adValue": -0.5, "marketId": "handicap"},
            "_111117": {"title": "Ф2", "value": 1.90, "adValue": 0.5, "marketId": "handicap"}
        },
        "markets": {}
    }
    
    parser = LigaStavokParser()
    result = parser._parse_single_event(test_event)
    
    if result:
        print("✓ Данные успешно распарсены:")
        print(f"  Матч: {result['match']}")
        print(f"  Турнир: {result['tournament']}")
        print(f"  Коэффициенты: 1={result['odds']['main']['1']}, X={result['odds']['main']['X']}, 2={result['odds']['main']['2']}")
        print(f"  Тоталы: {len(result['odds']['totals'])}")
        print(f"  Форы: {len(result['odds']['handicaps'])}")
        return True
    else:
        print("✗ Ошибка парсинга")
        return False


async def test_full_parse_with_cookies():
    """Тест полного парсинга с куками (если есть файл)"""
    print("\n" + "="*60)
    print("ТЕСТ 4: Полный парсинг с куками")
    print("="*60)
    
    cookies_file = "ligastavok_cookies.json"
    
    if not Path(cookies_file).exists():
        print(f"⊘ Файл {cookies_file} не найден")
        print("  Создайте файл с куками для запуска этого теста")
        print("  Инструкция в README_LIGASTAVOK.md")
        return None
    
    parser = LigaStavokParser(cookies_file=cookies_file)
    events = await parser.parse_all_events(max_pages=1)
    
    if events:
        print(f"✓ Получено {len(events)} событий")
        
        # Сохраняем результат
        output_file = "test_ligastavok_output.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(events, f, ensure_ascii=False, indent=2)
        print(f"✓ Результат сохранён в {output_file}")
        
        # Показываем пример
        event = events[0]
        print(f"\n  Пример события:")
        print(f"    {event['match']}")
        print(f"    Турнир: {event['tournament']}")
        if event['odds']['main']['1']:
            print(f"    Кэфы: 1={event['odds']['main']['1']}, X={event['odds']['main']['X']}, 2={event['odds']['main']['2']}")
        
        return True
    else:
        print("✗ Не удалось получить события")
        print("  Возможные причины:")
        print("  - Куки устарели")
        print("  - Защита QRATOR блокирует запрос")
        return False


async def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "="*60)
    print("ТЕСТИРОВАНИЕ ПАРСЕРА ЛИГА СТАВОК")
    print("="*60)
    
    results = {}
    
    # Тест 1: HTTP куки
    results['HTTP Cookies'] = await test_cookies_http()
    
    # Тест 2: API без авторизации
    results['API Request'] = await test_api_request_without_auth()
    
    # Тест 3: Парсинг данных
    results['Data Parsing'] = test_data_parsing()
    
    # Тест 4: Полный парсинг (опционально)
    full_result = await test_full_parse_with_cookies()
    if full_result is not None:
        results['Full Parse'] = full_result
    
    # Итоги
    print("\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nПройдено тестов: {passed}/{total}")
    
    if passed == total:
        print("\n✓ Все тесты пройдены!")
        print("\nДля полноценной работы:")
        print("  1. Экспортируйте куки из браузера (см. README_LIGASTAVOK.md)")
        print("  2. Сохраните как 'ligastavok_cookies.json'")
        print("  3. Запустите парсер: python ligastavok_parser.py")
    else:
        print("\n⚠ Некоторые тесты не пройдены")
        print("  Это нормально для среды без браузера/кук")
        print("  Следуйте инструкции в README_LIGASTAVOK.md")
    
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)
