# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path(r'D:\stock\tool\stock\concept_data')

keywords = ['玻璃基板', 'TGV', 'ABF', '载板', '封装载板', 'CoWoS', '先进封装', '封装']

results = {}

for kw in keywords:
    results[kw] = []

for f in base.glob('*_concepts.json'):
    try:
        j = json.loads(f.read_text(encoding='utf-8'))
        code = j.get('stock_code', '')
        name = j.get('stock_name', '')
        already_added = set()

        for kw in keywords:
            # 搜索概念名称和reason
            for c in j.get('concepts', []):
                cname = c.get('name', '')
                creason = c.get('reason', '')
                if (kw in cname or kw in creason) and code not in already_added:
                    results[kw].append({'code': code, 'name': name, 'matched': cname})
                    already_added.add(code)
                    break

            # 搜索theme_points
            for t in j.get('theme_points', []):
                content = (t.get('content', '') + t.get('title', '') + t.get('summary', ''))
                if kw in content and code not in already_added:
                    results[kw].append({'code': code, 'name': name, 'matched': kw})
                    already_added.add(code)
                    break
    except:
        pass

for kw in keywords:
    print(f'\n=== {kw} ({len(results[kw])}只) ===')
    for r in results[kw]:
        print(f'{r["code"]} {r["name"]}: {r["matched"]}')
