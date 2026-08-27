# -*- coding: utf-8 -*-
"""
Backfill macd_signals for a missing date (e.g. 2026-08-25) from local kline.
纯本地：MACD(12,26,9) DIF>0 + 5日/10日涨幅过滤（创业板 300/301 开头），
缠论字段复用 sheet6_wencai.py 的 chan_score（从源码提取，避免 import 执行）。
用法: python backfill_macd_date.py 2026-08-25
"""
import sys, re
import numpy as np
import pandas as pd
import duckdb
from datetime import datetime

TARGET = sys.argv[1] if len(sys.argv) > 1 else '2026-08-25'

# --- extract chan_score from sheet6_wencai.py without executing the script ---
src = open(r'D:\stock\tool\stock\sheet6_wencai.py', encoding='utf-8').read()
start = src.index('def chan_score(')
end = src.index('\n# =====', start)
ns = {'np': np}
exec(src[start:end], ns)
chan_score = ns['chan_score']

con = duckdb.connect(r'D:\stock\tool\stock\data\stock.duckdb')
exists = con.execute("select count(*) from macd_signals where date=?::DATE", [TARGET]).fetchone()[0]
if exists:
    print(f'{TARGET} already has {exists} rows, delete first if rerun needed'); sys.exit(0)

kl = con.execute(f"""
    SELECT code, date, open, high, low, close, volume FROM kline
    WHERE code LIKE '30%' AND date <= '{TARGET}'::DATE
    ORDER BY code, date
""").df()
print(f'创业板 kline rows: {len(kl)}, stocks: {kl.code.nunique()}')

names = dict(con.execute("select code, name from stock_meta").fetchall())
ts = pd.Timestamp.now()

rows_5d, rows_10d = [], []
for code, g in kl.groupby('code'):
    g = g.sort_values('date').tail(80).reset_index(drop=True)
    if len(g) < 30:
        continue
    if str(g.date.iloc[-1])[:10] != TARGET:
        continue
    c = g.close.values.astype(float)
    # MACD 12/26/9 -> DIF
    ema12 = pd.Series(c).ewm(span=12, adjust=False).mean()
    ema26 = pd.Series(c).ewm(span=26, adjust=False).mean()
    dif = ema12 - ema26
    macd_val = float(dif.iloc[-1])
    if macd_val <= 0:
        continue
    gain5 = (c[-1] / c[-6] - 1) * 100 if len(c) >= 6 else 0
    gain10 = (c[-1] / c[-11] - 1) * 100 if len(c) >= 11 else 0
    sig = None
    if gain5 > 10:
        sig = ('5d_10pct', round(gain5, 2))
    elif gain10 > 20:
        sig = ('10d_20pct', round(gain10, 2))
    if not sig:
        continue
    try:
        score, details = chan_score(g)
    except Exception:
        score, details = 0.0, {}
    rows = rows_5d if sig[0] == '5d_10pct' else rows_10d
    rows.append((code, names.get(code, code), pd.Timestamp(TARGET), sig[0], macd_val, sig[1],
                 score, details.get('position', ''), details.get('trend', ''),
                 details.get('fx', '无分型'), details.get('bc', details.get('bcie', '无背驰')),
                 None, ts))

for rows in (rows_5d, rows_10d):
    for r in rows:
        con.execute("""INSERT INTO macd_signals (code, name, date, signal_type, macd, gain_pct,
            score, position, trend, fx, bcie, raw_data, fetch_time)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", list(r))
con.commit()
print(f'inserted: 5d_10pct={len(rows_5d)}, 10d_20pct={len(rows_10d)}')
print(con.execute("select date, signal_type, count(*) from macd_signals where date=?::DATE group by 1,2", [TARGET]).fetchall())
