# -*- coding: utf-8 -*-
"""
映射数据统一入库：board_members + stock_industry_sw
====================================================
来源:
  1. data/industry_members.json   -> board_members (board_type='THS行业', 问财)
  2. data/concept_data/*.json     -> board_members (board_type='THS概念', 10jqka F10)
  3. data/industry_data/*.json    -> stock_industry_sw (申万三级, 10jqka field.html)
幂等: 全量重建（delete + insert），可重复运行。
用法: python scripts/db_import_members.py
"""
import json
from pathlib import Path
from datetime import datetime
import duckdb

ROOT = Path(__file__).parent.parent
DB = ROOT / 'data' / 'stock.duckdb'
ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

con = duckdb.connect(str(DB))
con.execute("""CREATE TABLE IF NOT EXISTS board_members (
    board_name VARCHAR NOT NULL,
    board_type VARCHAR NOT NULL,
    stock_code VARCHAR NOT NULL,
    updated_at VARCHAR,
    PRIMARY KEY (board_name, board_type, stock_code)
)""")
con.execute("""CREATE TABLE IF NOT EXISTS stock_industry_sw (
    stock_code VARCHAR PRIMARY KEY,
    sw_l1 VARCHAR, sw_l2 VARCHAR, sw_l3 VARCHAR,
    sw_l3_members INTEGER,
    updated_at VARCHAR
)""")

con.execute("""CREATE TABLE IF NOT EXISTS concept_leaders (
    concept_name VARCHAR PRIMARY KEY,
    leader_codes VARCHAR,
    updated_at VARCHAR
)""")

# 1. THS行业（问财）
im = json.load(open(ROOT / 'data' / 'industry_members.json', encoding='utf-8'))
rows = [(b, 'THS行业', c, ts) for b, codes in im.items() for c in codes]
con.execute("DELETE FROM board_members WHERE board_type='THS行业'")
con.executemany("INSERT INTO board_members VALUES (?,?,?,?)", rows)
print(f'THS行业: {len(im)} boards, {len(rows)} memberships')

# 2. THS概念（F10 concept_data）
rows = []
n_files = 0
for f in (ROOT / 'data' / 'concept_data').glob('*_concepts.json'):
    d = json.load(open(f, encoding='utf-8'))
    code = f.stem.replace('_concepts', '')
    n_files += 1
    for c in d.get('concepts', []):
        if c.get('name'):
            rows.append((c['name'], 'THS概念', code, ts))
con.execute("DELETE FROM board_members WHERE board_type='THS概念'")
con.executemany("INSERT INTO board_members VALUES (?,?,?,?)", rows)
print(f'THS概念: {n_files} stocks, {len(rows)} memberships')

# 3. 申万行业（field.html）
rows = []
for f in (ROOT / 'data' / 'industry_data').glob('*_industry.json'):
    d = json.load(open(f, encoding='utf-8'))
    if d.get('sw_l3'):
        rows.append((d['stock_code'], d['sw_l1'], d['sw_l2'], d['sw_l3'], d.get('sw_l3_members'), ts))
con.execute('DELETE FROM stock_industry_sw')
con.executemany("INSERT INTO stock_industry_sw VALUES (?,?,?,?,?,?)", rows)
print(f'申万行业: {len(rows)} stocks')

# 4. 概念龙头股（concept_data 的 top_stocks 字段，0 额外成本）
leaders = {}
for f in (ROOT / 'data' / 'concept_data').glob('*_concepts.json'):
    d = json.load(open(f, encoding='utf-8'))
    for c in d.get('concepts', []):
        if c.get('name') and c.get('top_stocks'):
            leaders[c['name']] = c['top_stocks']   # 后写覆盖 = 全市场最新一致
con.execute('DELETE FROM concept_leaders')
con.executemany('INSERT INTO concept_leaders VALUES (?,?,?)',
                [(k, v, ts) for k, v in leaders.items()])
print(f'概念龙头: {len(leaders)} 个概念')

print('\n=== 校验 ===')
print(con.execute("""SELECT board_type, count(distinct board_name) boards, count(*) rows
    FROM board_members GROUP BY 1""").fetchall())
print('股票数: stock_meta', con.execute('select count(*) from stock_meta').fetchone()[0],
      '| sw', con.execute('select count(*) from stock_industry_sw').fetchone()[0])
orphan = con.execute("""select count(*) from board_members m
    left join stock_meta s on s.code = m.stock_code where s.code is null""").fetchone()[0]
print('board_members 孤儿代码(不在 stock_meta):', orphan)
con.close()
print('[DONE]')
