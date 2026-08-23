# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path(r'D:\stock\tool\stock\concept_data')
keyword = 'MCU'
results = []

for f in base.glob('*_concepts.json'):
    try:
        j = json.loads(f.read_text(encoding='utf-8'))
        code = j.get('stock_code', '')
        name = j.get('stock_name', '')

        matched_concepts = []
        for c in j.get('concepts', []):
            if keyword in c.get('name', '') or keyword in c.get('reason', ''):
                matched_concepts.append(c.get('name', ''))

        matched_themes = []
        for t in j.get('theme_points', []):
            content = t.get('content', '') + t.get('title', '') + t.get('summary', '')
            if keyword in content:
                matched_themes.append(t.get('title', ''))

        if matched_concepts or matched_themes:
            results.append({
                'code': code,
                'name': name,
                'concepts': matched_concepts,
                'themes': matched_themes
            })
    except:
        pass

print(f'找到 {len(results)} 只相关股票:')
for r in results:
    concepts_str = ' | '.join(r['concepts'][:3])
    print(f'{r["code"]} {r["name"]}: {concepts_str}')
