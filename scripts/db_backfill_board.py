# -*- coding: utf-8 -*-
"""回填 non_top3_stocks.board_name/board_pct：用 stock_meta 概念 + board_history 匹配"""
import duckdb
import json
import pandas as pd
from pathlib import Path

DB = Path('data/stock.duckdb')
conn = duckdb.connect(str(DB))

rows = conn.execute("""
    SELECT DISTINCT date, stock_code, stock_name FROM non_top3_stocks
    WHERE board_name IS NULL OR board_name = ''
""").fetchall()
print(f'待回填: {len(rows)} 行')

# 概念映射缓存
meta = conn.execute("SELECT code, concepts FROM stock_meta WHERE concepts IS NOT NULL").fetchall()
concepts_map = {}
for code, cj in meta:
    try:
        concepts_map[code] = [c['name'] for c in json.loads(cj)]
    except Exception:
        concepts_map[code] = []

# 按日期取概念板块涨幅
def get_concept_pcts(date_str):
    df = conn.execute(
        "SELECT board_name, pct FROM board_history WHERE board_type='概念' AND date::VARCHAR = ?",
        [date_str]).fetchall()
    return dict(df)

updated = 0
for date, code, name in rows:
    date_str = str(date)[:10]
    pcts = get_concept_pcts(date_str)
    cands = concepts_map.get(code, [])
    best = None
    best_pct = -999
    for c in cands:
        if c in pcts and pcts[c] > best_pct:
            best = c
            best_pct = pcts[c]
    if best:
        conn.execute(
            "UPDATE non_top3_stocks SET board_name=?, board_pct=? WHERE date=? AND stock_code=?",
            [best, best_pct, date, code])
        updated += 1

conn.commit()
print(f'[OK] 回填 {updated}/{len(rows)} 行（无概念匹配的保留空）')
conn.close()
