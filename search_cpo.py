# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path(r'D:\stock\tool\stock\concept_data')
keywords = ['CPO', '共封装', 'TGV', '玻璃基板', '光互连', '光通信']
results = []

for f in base.glob('*_concepts.json'):
    try:
        j = json.loads(f.read_text(encoding='utf-8'))
        code = j.get('stock_code', '')
        name = j.get('stock_name', '')

        matched = []
        for c in j.get('concepts', []):
            for kw in keywords:
                if kw in c.get('name', '') or kw in c.get('reason', ''):
                    matched.append(c.get('name', ''))
                    break

        if matched:
            results.append({'code': code, 'name': name, 'concepts': list(set(matched))[:5]})
    except:
        pass

print(f'=== 找到 {len(results)} 只相关股票 ===')
for r in results:
    concepts_str = ' | '.join(r['concepts'])
    print(f'{r["code"]} {r["name"]}: {concepts_str}')
