# -*- coding: utf-8 -*-
"""
从 akshare.stock_sector_spot 一次性导入概念板块当日数据到 DB。

**DEPRECATED (2026-08-28, 方案A)**：新浪口径与 THS 375 概念不一致，会污染 board_history。
已改用 `merge_board_daily.py --include-concept`。本脚本保留仅作历史参考，运行即退出。

用法：
  python scripts/db_import_concepts_spot.py
"""
import sys
print('[DEPRECATED] 新浪概念口径会污染 board_history，已改用 merge_board_daily.py --include-concept')
sys.exit(2)
from pathlib import Path
from datetime import datetime, time as dtime
import duckdb
import pandas as pd
import akshare as ak

ROOT = Path(__file__).parent.parent if __name__ == '__main__' else Path.cwd()
if not (ROOT / 'data' / 'stock.duckdb').exists():
    ROOT = Path.cwd()
DB_PATH = ROOT / 'data' / 'stock.duckdb'


def main():
    print('[INFO] Fetching concept board data from akshare (1 API call)...')
    df = ak.stock_sector_spot(indicator='概念')
    print(f'[OK] Got {len(df)} concept boards')

    # 准备数据
    # 非交易时段（凌晨）：spot 返回的是上一交易日收盘数据
    # 所以 9:15 前实际交易日 = 昨天
    now = datetime.now()
    if now.time() < dtime(9, 15):
        target_date = (now - pd.Timedelta(days=1)).date()
    else:
        target_date = now.date()
    print(f'[INFO] Target trade date: {target_date}')
    rows = []
    for _, row in df.iterrows():
        rows.append({
            'board_name': row['板块'],
            'board_type': '概念',
            'date': target_date,
            'close': float(row['平均价格']),  # 用平均价格作为 close（ak 没直接给收盘指数）
            'pct': float(row['涨跌幅']),
        })

    df_out = pd.DataFrame(rows)

    conn = duckdb.connect(str(DB_PATH))
    # 删除同日期的概念数据
    deleted = conn.execute(
        "DELETE FROM board_history WHERE board_type='概念' AND date = ?",
        [target_date]
    ).fetchone()
    print(f'[OK] Deleted existing: {deleted[0] if deleted else 0} rows')

    # 插入新数据
    conn.execute("INSERT INTO board_history SELECT * FROM df_out")
    print(f'[OK] Inserted {len(df_out)} concept boards for {target_date}')

    # 验证
    count = conn.execute(
        "SELECT COUNT(*) FROM board_history WHERE date = ? AND board_type='概念'",
        [target_date]
    ).fetchone()[0]
    print(f'[OK] DB now has {count} concept boards for {target_date}')

    conn.close()
    print('\n[DONE]')


if __name__ == '__main__':
    main()
