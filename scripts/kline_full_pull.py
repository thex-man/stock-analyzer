# -*- coding: utf-8 -*-
"""
增量拉取主板+创业板 K线 → kline 表（v2 动态日期版）
用途：每日增量 + 历史 >6% 个股本地计算
用法: python scripts/kline_full_pull.py            # 增量：只拉缺最新交易日的股票
      python scripts/kline_full_pull.py --full     # 全量重拉
"""
import argparse
import sys, time
from pathlib import Path
from datetime import datetime, date, timedelta
import duckdb
import pandas as pd
import akshare as ak

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / 'data' / 'stock.duckdb'


def get_target_date():
    """交易日 = 今天（9:15 前 = 昨天）"""
    now = datetime.now()
    if now.time() < datetime.strptime('09:15', '%H:%M').time():
        return (now - timedelta(days=1)).date()
    return now.date()


TARGET = get_target_date()
START = (TARGET - timedelta(days=25)).strftime('%Y-%m-%d')
END = TARGET.strftime('%Y-%m-%d')


def sina_symbol(code):
    return ('sh' if code.startswith('6') else 'sz') + code


def main():
    conn = duckdb.connect(str(DB_PATH))
    # 主板+创业板: 60xxxx 00xxxx 30xxxx
    codes = [c for (c,) in conn.execute("""
        SELECT code FROM stock_meta
        WHERE code LIKE '60%' OR code LIKE '00%' OR code LIKE '30%'
    """).fetchall()]
    print(f'Total stocks: {len(codes)}, target date: {TARGET}')

    import sys
    full = '--full' in sys.argv
    if full:
        todo = codes
    else:
        have = {c for (c,) in conn.execute(
            "SELECT DISTINCT code FROM kline WHERE date = ?", [TARGET]).fetchall()}
        todo = [c for c in codes if c not in have]
    print(f'Already have target date: {len(codes) - len(todo)}, to pull: {len(todo)}')

    ok, fail = 0, 0
    fails = []
    t0 = time.time()
    for i, code in enumerate(todo, 1):
        try:
            df = ak.stock_zh_a_daily(symbol=sina_symbol(code), start_date=START, end_date=END, adjust='')
            if df is None or df.empty:
                fail += 1
                continue
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            df['code'] = code
            df['date'] = pd.to_datetime(df['date']).dt.date
            conn.execute("DELETE FROM kline WHERE code=? AND date >= ?", [code, START])
            conn.execute("INSERT INTO kline SELECT code, date, open, high, low, close, volume FROM df")
            ok += 1
        except Exception as e:
            fail += 1
            if len(fails) < 20:
                fails.append((code, str(e)[:50]))
        if i % 100 == 0:
            conn.commit()
            elapsed = time.time() - t0
            print(f'  [{i}/{len(todo)}] ok={ok} fail={fail} elapsed={elapsed:.0f}s', flush=True)
        time.sleep(0.15)

    conn.commit()
    n = conn.execute("SELECT COUNT(*) FROM kline").fetchone()[0]
    n_codes = conn.execute("SELECT COUNT(DISTINCT code) FROM kline").fetchone()[0]
    conn.close()
    print(f'\n[DONE] pulled ok={ok} fail={fail}')
    print(f'kline total: {n} rows, {n_codes} codes')
    if fails[:5]:
        print('sample fails:', fails[:5])


if __name__ == '__main__':
    main()
