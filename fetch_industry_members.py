# -*- coding: utf-8 -*-
"""Fetch THS industry membership via wencai -> data/industry_members.json

One wencai query per industry (~40s each, 90 total). Resume-safe:
industries already in the JSON are skipped. Rerun until all 90 done.
"""
import sys, json, time
sys.path.insert(0, r'D:\stock\tool\stock')
from pathlib import Path
from stock_data_source import wencai
import duckdb

OUT = Path(r'D:\stock\tool\stock\data\industry_members.json')
result = json.load(open(OUT, encoding='utf-8')) if OUT.exists() else {}

con = duckdb.connect(r'D:\stock\tool\stock\data\stock.duckdb', read_only=True)
inds = [r[0] for r in con.execute(
    "select distinct board_name from board_history where board_type='行业' order by 1").fetchall()]
todo = [n for n in inds if n not in result or len(result[n]) < 3]
print(f'{len(inds)} industries, {len(todo)} to fetch')

fail = []
for i, n in enumerate(todo, 1):
    ok = False
    for attempt in (1, 2):
        try:
            r = wencai(f'所属同花顺行业为{n}', perpage=200)
            df = r.get('datas')
            if df is not None and len(df):
                codes = [str(c).replace('.SZ', '').replace('.SH', '').replace('.BJ', '')
                         .replace('sz', '').replace('sh', '').replace('bj', '').zfill(6)
                         for c in df['股票代码']]
                result[n] = codes
                ok = True
                break
        except Exception as e:
            print(f'  ERR {n} (attempt {attempt}): {str(e)[:60]}')
            time.sleep(5)
    if not ok:
        fail.append(n)
        result.setdefault(n, [])
    json.dump(result, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'[{i}/{len(todo)}] {n}: {len(result.get(n, []))} stocks')
    time.sleep(1)

n_empty = [n for n, v in result.items() if len(v) < 3]
print(f'DONE: {len(result)} industries, {sum(len(v) for v in result.values())} memberships')
print(f'empty/retry-needed ({len(n_empty)}):', n_empty)
