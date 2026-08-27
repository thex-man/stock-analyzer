# -*- coding: utf-8 -*-
"""
DuckDB 数据库初始化 + 表结构创建

数据库路径：D:\\stock\\tool\\stock\\data\\stock.duckdb

表设计（4 张）：
  1. stock_meta      - 股票元数据 + 概念（替换 concept_data/*.json）
  2. kline           - K 线行情（替换 kline_cache/*.csv）
  3. board_history   - 板块历史（替换 data/board_history_ths/history_*.json）
  4. macd_signals    - MACD/缠论等衍生指标（替换 Excel Sheet6/7）

用法：
  python scripts/db_init.py             # 创建库 + 表（如已存在则跳过创建）
  python scripts/db_init.py --recreate  # 删除重建（清空所有数据！）
"""
import sys
import os
import duckdb
import argparse
from pathlib import Path

# 数据库路径
DB_PATH = Path(__file__).parent.parent / 'data' / 'stock.duckdb'

SCHEMA_SQL = """
-- 1. 股票元数据 + 概念（替换 5688 个 JSON）
CREATE TABLE IF NOT EXISTS stock_meta (
  code           VARCHAR PRIMARY KEY,        -- 6位代码（如 000001）
  name           VARCHAR NOT NULL,           -- 股票名称
  concepts       JSON,                       -- 概念列表（JSON 数组）
  theme_points   JSON,                       -- 主题要点（JSON 数组）
  fetch_time     TIMESTAMP,
  total_concepts INTEGER
);
CREATE INDEX IF NOT EXISTS idx_stock_meta_name ON stock_meta(name);

-- 2. K 线行情（替换 1403 个 CSV）
CREATE TABLE IF NOT EXISTS kline (
  code    VARCHAR NOT NULL,
  date    DATE    NOT NULL,
  open    DOUBLE,
  high    DOUBLE,
  low     DOUBLE,
  close   DOUBLE,
  volume  BIGINT,
  PRIMARY KEY (code, date)
);
CREATE INDEX IF NOT EXISTS idx_kline_date ON kline(date);
CREATE INDEX IF NOT EXISTS idx_kline_code ON kline(code);

-- 3. 板块历史（替换 board_history_ths/history_*.json）
CREATE TABLE IF NOT EXISTS board_history (
  board_name VARCHAR NOT NULL,
  board_type VARCHAR NOT NULL,              -- 行业 / 概念
  date       DATE    NOT NULL,
  close      DOUBLE,
  pct        DOUBLE,                        -- 涨跌幅（%）
  PRIMARY KEY (board_name, date)
);
CREATE INDEX IF NOT EXISTS idx_board_history_date ON board_history(date);
CREATE INDEX IF NOT EXISTS idx_board_history_type ON board_history(board_type);

-- 4. MACD / 缠论等衍生信号
CREATE TABLE IF NOT EXISTS macd_signals (
  code         VARCHAR NOT NULL,
  name         VARCHAR,
  date         DATE    NOT NULL,
  signal_type  VARCHAR NOT NULL,            -- 5d_10pct / 10d_20pct / v2_5d / v2_10d
  macd         DOUBLE,
  gain_pct     DOUBLE,                      -- 5日/10日涨幅
  score        DOUBLE,                      -- 缠论分数
  position     VARCHAR,                     -- 中枢位置
  trend        VARCHAR,                     -- 趋势
  fx           VARCHAR,                     -- 分型
  bcie         VARCHAR,                     -- 背驰
  raw_data     JSON,                        -- 完整数据（备用）
  fetch_time   TIMESTAMP,
  PRIMARY KEY (code, date, signal_type)
);
CREATE INDEX IF NOT EXISTS idx_macd_date ON macd_signals(date);
CREATE INDEX IF NOT EXISTS idx_macd_type ON macd_signals(signal_type);
CREATE INDEX IF NOT EXISTS idx_macd_score ON macd_signals(score DESC);

-- 元信息表
CREATE TABLE IF NOT EXISTS db_meta (
  key   VARCHAR PRIMARY KEY,
  value VARCHAR
);
"""


def init_db(db_path: Path = DB_PATH, recreate: bool = False):
    """初始化数据库"""
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if recreate and db_path.exists():
        print(f'[WARN] Deleting old DB: {db_path}')
        db_path.unlink()

    conn = duckdb.connect(str(db_path))
    print(f'[OK] Connected: {db_path}')
    if db_path.exists():
        print(f'   Size: {db_path.stat().st_size / 1024:.1f} KB')

    # 创建表
    for stmt in SCHEMA_SQL.split(';'):
        stmt = stmt.strip()
        if stmt:
            conn.execute(stmt)

    print('[OK] Created 4 tables: stock_meta / kline / board_history / macd_signals')

    # 显示表清单
    tables = conn.execute("SHOW TABLES").fetchall()
    print('\nCurrent tables:')
    for t in tables:
        count = conn.execute(f'SELECT COUNT(*) FROM {t[0]}').fetchone()[0]
        print(f'  - {t[0]}: {count} 行')

    conn.close()
    return db_path


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='DuckDB 数据库初始化')
    parser.add_argument('--recreate', action='store_true', help='删除重建')
    parser.add_argument('--db', type=str, help='数据库路径（默认 data/stock.duckdb）')
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else DB_PATH
    init_db(db_path, recreate=args.recreate)
    print(f'\n[DONE] {db_path}')
