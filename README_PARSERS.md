# Парсеры букмекеров

## ✅ 24bet.ru — ПОЛНОСТЬЮ РАБОЧИЙ

**Файл:** `24bet_parser.py`

### Запуск
```bash
python 24bet_parser.py
```

### Возможности
- Получает ~11,000 событий (Live + Prematch)
- Автоматическое обновление каждые 5 секунд через версионирование
- Парсит коэффициенты (1X2, тоталы, форы)
- Извлекает live-счета в реальном времени
- Не требует cookies/авторизации

### Пример использования в коде
```python
from 24bet_parser import TwentyFourBetParser

parser = TwentyFourBetParser()
parser.run(interval=5, max_iterations=3)

# Получить все live-события
live_events = parser.get_all_events(only_live=True, only_with_odds=True)

# Получить конкретное событие
summary = parser.get_event_summary(event_id)
```

---

## ⚠️ bet-m.ru — ТРЕБУЮТСЯ COOKIES

**Файл:** `betm_final_parser.py`

### Проблема
Сайт использует строгую защиту Cloudflare с JavaScript-challenge. 
Автоматические запросы блокируются (403 Forbidden).

### Решение: ручное получение cookies

1. **Откройте браузер** (Chrome/Firefox/Yandex)
2. Перейдите на https://sport.bet-m.ru/
3. **Откройте DevTools** (F12)
4. Перейдите во вкладку **Application → Cookies → https://sport.bet-m.ru**
5. **Скопируйте 3 значения:**
   - `cf_clearance`
   - `__cf_bm`
   - `_cfuvid`
6. **Вставьте их в файл** `betm_final_parser.py` в переменную `MANUAL_COOKIES`:

```python
MANUAL_COOKIES = {
    'cf_clearance': 'ваше_значение_из_браузера',
    '__cf_bm': 'ваше_значение_из_браузера',
    '_cfuvid': 'ваше_значение_из_браузера'
}
```

7. **Запустите парсер:**
```bash
python betm_final_parser.py
```

### Альтернатива: установка cookies через метод
```python
from betm_final_parser import BetMParser

parser = BetMParser()
parser.set_manual_cookies({
    'cf_clearance': '...',
    '__cf_bm': '...',
    '_cfuvid': '...'
})
parser.run(interval=10, max_iterations=2)
```

---

## 📊 Сравнение парсеров

| Параметр | 24bet.ru | bet-m.ru |
|----------|----------|----------|
| Статус | ✅ Работает | ⚠️ Требует cookies |
| Защита | Нет | Cloudflare JS Challenge |
| Live события | ✅ Да | ✅ Да (с cookies) |
| Коэффициенты | ✅ Да | ✅ Да (с cookies) |
| Авто-обновление | ✅ Да | ✅ Да (с cookies) |
| Сложность | Низкая | Средняя |

---

## 🔧 Требования

```bash
pip install requests
```

Для bet-m.ru с Playwright (если есть место):
```bash
pip install playwright
playwright install chromium
```
