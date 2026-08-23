# -*- coding: utf-8 -*-
"""系统配置"""
import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
WAREHOUSE_DIR = PROJECT_ROOT / "warehouse"
FACTORS_DIR = PROJECT_ROOT / "factors"
SIGNALS_DIR = PROJECT_ROOT / "signals"
ENGINE_DIR = PROJECT_ROOT / "engine"
BACKTEST_DIR = PROJECT_ROOT / "backtest"
REPORTS_DIR = PROJECT_ROOT / "reports"
UTILS_DIR = PROJECT_ROOT / "utils"

# 数据库配置（DuckDB/Postgres）
DB_PATH = WAREHOUSE_DIR / "stock_warehouse.db"

# 数据源配置
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")

# 交易日历
TRADING_DAYS_FILE = DATA_DIR / "trading_calendar.csv"

# 利好消息存储
GOOD_NEWS_FILE = DATA_DIR / "利好消息.xlsx"

# 评估参数默认值
DEFAULT_HOLDING_PERIOD = 5      # 持有期（交易日）
DEFAULT_N_STOCKS = 20           # 持仓股票数量
DEFAULT_TOPIC_HOTNESS_THRESHOLD = 0.7  # 热点阈值
