# -*- coding: utf-8 -*-
"""
回补历史 Top3 / 非Top3 数据
============================
- top3_stocks: 从 board_history 取每日 Top3 行业板块（个股未知，显示 '—'）
- non_top3_stocks: 从 kline 计算每日涨幅>6%（仅覆盖 kline 内 1403 只创业板股票）
幂等：按日期 DELETE + INSERT
"""
import duckdb
import pandas as pd
from pathlib import Path

DB = Path('data/stock.duckdb')
conn = duckdb.connect(str(DB))

N_DAYS = 10
ts = pd.Timestamp.now()

# 最近 N_DAYS 交易日（从 board_history）
dates = [d for (d,) in conn.execute(
    f"SELECT DISTINCT date FROM board_history ORDER BY date DESC LIMIT {N_DAYS}").fetchall()]
print(f'回补日期: {[str(d) for d in dates]}')

# ---- 1. top3_stocks 回补（Top3 板块 + '—' 个股） ----
top3_rows = []
for d in dates:
    boards = conn.execute("""
        SELECT board_name, pct FROM board_history
        WHERE board_type='行业' AND date=? ORDER BY pct DESC LIMIT 3
    """, [d]).fetchall()
    for rank, (bname, bpct) in enumerate(boards, 1):
        top3_rows.append((str(d)[:10], bname, '行业', bpct, rank, '-', '—', 0, ts))

df = pd.DataFrame(top3_rows, columns=['date', 'board_name', 'board_type', 'board_pct', 'rank_', 'stock_code', 'stock_name', 'stock_pct', 'fetch_time'])
for d in df['date'].unique():
    # 先清掉该日期所有占位行，保留真实个股数据
    conn.execute("DELETE FROM top3_stocks WHERE date::VARCHAR=? AND stock_code='-'", [d])
conn.execute("""INSERT INTO top3_stocks (date, board_name, board_type, board_pct, rank_, stock_code, stock_name, stock_pct, fetch_time)
                SELECT date::DATE, board_name, board_type, board_pct, rank_, stock_code, stock_name, stock_pct, fetch_time FROM df""")
print(f'[OK] top3_stocks 回补 {len(df)} 行')

# ---- 2. non_top3_stocks 回补（kline 涨幅>6%） ----
kl = conn.execute("""
    SELECT code, date, close,
           LAG(close) OVER (PARTITION BY code ORDER BY date) AS prev_close
    FROM kline
    WHERE date IN (SELECT DISTINCT date FROM board_history ORDER BY date DESC LIMIT 10)
""").df()
kl = kl.dropna(subset=['prev_close'])
kl['pct'] = (kl['close'] / kl['prev_close'] - 1) * 100
gainers = kl[kl['pct'] > 6].copy()
print(f'kline 中 >6%: {len(gainers)} 行')

# 股票名 + 概念
meta = {c: n for c, n in conn.execute("SELECT code, name FROM stock_meta").fetchall()}
concepts = {}
for code, cj in conn.execute("SELECT code, concepts FROM stock_meta WHERE concepts IS NOT NULL").fetchall():
    import json as _json
    try:
        concepts[code] = [c['name'] for c in _json.loads(cj)]
    except Exception:
        concepts[code] = []

# 每日概念板块涨幅（用于匹配所属概念 + 排除 Top3 板块）
rows_added = 0
# 保护最新真实问财数据日（有全市场 wencai 数据的日期），其余历史日期全量重算
REAL_DATES = {str(d)[:10] for (d,) in conn.execute(
    "SELECT DISTINCT date FROM non_top3_stocks WHERE stock_pct IS NOT NULL AND date = (SELECT MAX(date) FROM non_top3_stocks)").fetchall()}
for d in gainers['date'].unique():
    d_str = str(d)[:10]
    if d_str in REAL_DATES:
        print(f'  non_top3 {d_str}: wencai 真实数据，跳过')
        continue
    concept_pcts = dict(conn.execute(
        "SELECT board_name, pct FROM board_history WHERE board_type='概念' AND date::VARCHAR=?", [d_str]).fetchall())
    top3_boards = {b for b, _ in conn.execute(
        "SELECT board_name, pct FROM board_history WHERE board_type='行业' AND date::VARCHAR=? ORDER BY pct DESC LIMIT 3", [d_str]).fetchall()}
    sub = gainers[gainers['date'] == d]
    recs = []
    for _, r in sub.iterrows():
        code = r['code']
        # 找所属概念（排除 Top3 板块）
        best, best_pct = '', 0
        for c in concepts.get(code, []):
            if c in top3_boards:
                continue
            if c in concept_pcts and concept_pcts[c] > best_pct:
                best, best_pct = c, concept_pcts[c]
        recs.append((d_str, code, meta.get(code, code), best, best_pct, round(r['pct'], 2), ts))
    df2 = pd.DataFrame(recs, columns=['date', 'stock_code', 'stock_name', 'board_name', 'board_pct', 'stock_pct', 'fetch_time'])
    conn.execute("DELETE FROM non_top3_stocks WHERE date::VARCHAR=?", [d_str])
    conn.execute("""INSERT INTO non_top3_stocks (date, stock_code, stock_name, board_name, board_pct, stock_pct, fetch_time)
                    SELECT date::DATE, stock_code, stock_name, board_name, board_pct, stock_pct, fetch_time FROM df2""")
    rows_added += len(df2)
    print(f'  non_top3 {d_str}: +{len(df2)} 行（kline 子集）')

conn.commit()
print(f'\n[OK] non_top3_stocks 回补 {rows_added} 行')
for tbl in ['top3_stocks', 'non_top3_stocks']:
    df3 = conn.execute(f"SELECT date, COUNT(*) FROM {tbl} GROUP BY date ORDER BY date DESC").df()
    print(f'\n{tbl}:')
    print(df3.to_string())
conn.close()
