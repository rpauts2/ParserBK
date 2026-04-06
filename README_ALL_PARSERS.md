# Парсеры букмекерских контор РФ

## ✅ Полностью рабочие парсеры

### 1. 24bet.ru
- **Файл:** `24bet_parser.py`
- **API:** `https://line51.tf39be-resources.com/events/list`
- **Статус:** ✅ РАБОТАЕТ
- **Событий:** ~11,000 (Live + Prematch)
- **Запуск:** `python 24bet_parser.py`

### 2. Fonbet
- **Файл:** `fonbet_parser.py`
- **API:** `https://line-lb54-w.bk6bba-resources.com/ma/events/list`
- **Статус:** ✅ РАБОТАЕТ
- **Событий:** ~4,000+ (Live + Prematch)
- **Запуск:** `python fonbet_parser.py`

### 3. Liga Stavok
- **Файл:** `ligastavok_parser.py`
- **Статус:** ✅ РАБОТАЕТ

---

## ⚠️ Требуют настройки cookies (Cloudflare)

### 4. Bet-M
- **Файл:** `betm_final_parser.py`
- **API:** `https://sport.bet-m.ru`
- **Проблема:** Cloudflare protection
- **Решение:** Получить cookies из браузера или использовать Playwright

### 5. Leon
- **Файл:** `leon_parser.py`
- **Проблема:** Требуется авторизация/Cookies

### 6. Olimp
- **Файл:** `olimp_parser.py`
- **Проблема:** Требуется авторизация/Cookies

### 7. Melbet
- **Файл:** `melbet_parser.py`
- **Проблема:** Требуется авторизация/Cookies

### 8. BetBoom
- **Файл:** `betboom_parser.py`
- **Проблема:** Требуется авторизация/Cookies

### 9. Tenisi
- **Файл:** `tenisi_parser.py`
- **Проблема:** Требуется авторизация/Cookies

---

## 📋 Уже были готовы (от пользователя)
- Winline
- Pari
- Betcity
- Marathon
- Zenit
- Baltbet
- Bettery

---

## Быстрый старт

```bash
# Запустить рабочий парсер
python 24bet_parser.py
python fonbet_parser.py
python ligastavok_parser.py

# Для парсеров с Cloudflare нужно получить cookies:
# 1. Открыть сайт в браузере
# 2. DevTools → Application → Cookies
# 3. Скопировать cf_clearance, __cf_bm
# 4. Вставить в код parser.set_cookies({...})
```

## Структура ответа API

Все парсеры возвращают данные в формате:
```python
{
    'id': event_id,
    'team1': 'Команда 1',
    'team2': 'Команда 2',
    'start_time': '2026-04-04 18:00',
    'is_live': True/False,
    'score': '1:0',
    'timer': '45:00',
    'odds': {...}
}
```

## Обновление документации

Для добавления новых БК:
1. Создать файл `{bookmaker}_parser.py`
2. Реализовать класс с методами: `fetch_events()`, `parse_events()`, `run()`
3. Добавить в этот README
