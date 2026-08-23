# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path(r'D:\stock\tool\stock\concept_data')
keywords = ['人工智能', 'AI', '大模型', '科创板', '智谱', '算力', '云计算', '算法']

results = {}

for kw in keywords:
    results[kw] = []

for f in base.glob('*_concepts.json'):
    try:
        j = json.loads(f.read_text(encoding='utf-8'))
        code = j.get('stock_code', '')
        name = j.get('stock_name', '')
        already = set()

        for kw in keywords:
            for c in j.get('concepts', []):
                cname = c.get('name', '')
                if kw in cname and code not in already:
                    results[kw].append({'code': code, 'name': name, 'matched': cname})
                    already.add(code)
                    break

            for t in j.get('theme_points', []):
                content = t.get('content', '') + t.get('title', '') + t.get('summary', '')
                if kw in content and code not in already:
                    results[kw].append({'code': code, 'name': name, 'matched': kw})
                    already.add(code)
                    break
    except:
        pass

# 合并去重
all_codes = {}
for kw in keywords:
    for r in results[kw]:
        if r['code'] not in all_codes:
            all_codes[r['code']] = {'code': r['code'], 'name': r['name'], 'matched_kw': [r['matched']]}
        else:
            all_codes[r['code']]['matched_kw'].append(r['matched'])

print(f'AI相关股票共 {len(all_codes)} 只')
for code, info in sorted(all_codes.items()):
    kws = ' | '.join(info['matched_kw'][:5])
    print(f'{code} {info["name"]}: {kws}')
