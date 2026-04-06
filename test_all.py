import sys
import importlib

parsers_map = {
    "24bet": "parser_24bet",
    "Fonbet": "parser_fonbet",
    "Leon": "parser_leon",
    "Olimp": "parser_olimp",
    "Melbet": "parser_melbet",
    "BetCity": "parser_betcity",
    "Zenit": "parser_zenit",
    "LigaStavok": "parser_ligastavok"
}

results = []

for name, mod_name in parsers_map.items():
    try:
        # Динамический импорт
        module = importlib.import_module(mod_name)
        
        # Поиск класса парсера
        cls = None
        for attr in dir(module):
            if attr.endswith('Parser') and attr != 'object':
                cls = getattr(module, attr)
                break
        
        if cls:
            p = cls()
            if hasattr(p, 'fetch_data'):
                p.fetch_data()
            
            events = []
            if hasattr(p, 'get_all_events'):
                events = p.get_all_events()
            elif hasattr(p, 'events'):
                events = p.events
            
            total = len(events)
            live = 0
            for e in events:
                if isinstance(e, dict):
                    if e.get('place') == 'live' or e.get('betline') == 'inplay' or e.get('is_live'):
                        live += 1
                elif hasattr(e, 'is_live') and e.is_live:
                    live += 1
            
            prematch = total - live
            results.append((name, total, live, prematch, "OK"))
        else:
            results.append((name, 0, 0, 0, "No Class"))
    except Exception as e:
        results.append((name, 0, 0, 0, f"Error: {str(e)[:30]}"))

print(f"{'BOOKMAKER':<12} | {'TOTAL':<8} | {'LIVE':<6} | {'PREMATCH':<10} | {'STATUS'}")
print("-" * 55)
for name, total, live, pre, status in results:
    print(f"{name:<12} | {total:<8} | {live:<6} | {pre:<10} | {status}")
