# -*- coding: utf-8 -*-
"""Refetch THS board history 2026-08-01..08-27 for given board_type, overwrite DB rows.

Usage: python backfill_ths_range.py 行业|概念
One akshare call per board covering the full date range.
pct computed from consecutive closes within the series.
"""
import sys, time, duckdb, akshare as ak

bt = sys.argv[1]
START, END = '20260731', '20260827'
con = duckdb.connect(r'D:\stock\tool\stock\data\stock.duckdb')

cache = __import__('json').load(open(r'D:\stock\tool\stock\data\board_history_ths\history_20260728_20260827.json', encoding='utf-8'))
names = sorted(n for n, i in cache.items() if i.get('type') == bt)
print(f'{bt}: {len(names)} boards, range {START}-{END}')

fetch = ak.stock_board_industry_index_ths if bt == '行业' else ak.stock_board_concept_index_ths
ok, fail, total_rows = 0, 0, 0
for i, n in enumerate(names, 1):
    try:
        df = fetch(symbol=n, start_date=START, end_date=END)
        if df is None or df.empty:
            fail += 1; continue
        df = df.sort_values('日期')
        prev_c = None
        rows = []
        for _, r in df.iterrows():
            d = str(r['日期']).replace('-', '')
            if d < '20260801':          # keep 7/31 close as base only
                prev_c = float(r['收盘价']); continue
            c = float(r['收盘价'])
            p = round((c / prev_c - 1) * 100, 2) if prev_c else None
            rows.append((n, bt, f'{d[:4]}-{d[4:6]}-{d[6:]}', c, p))
            prev_c = c
        if rows:
            con.executemany("delete from board_history where board_name=? and board_type=?", [(n, bt)])
            con.executemany("insert into board_history values (?,?,?,?,?)", rows)
            total_rows += len(rows); ok += 1
    except Exception as e:
        fail += 1
        print(f'  FAIL {n}: {str(e)[:60]}')
    if i % 20 == 0 or i == len(names):
        print(f'  [{i}/{len(names)}] ok={ok} fail={fail} rows={total_rows}')
        sys.stdout.flush()
    time.sleep(0.2)
print(f'DONE {bt}: boards ok={ok} fail={fail}, rows={total_rows}')
