# -*- coding: utf-8 -*-
"""
AKShare 数据接入模块
====================
从 AKShare 拉取免费行情数据，无需 Token

支持:
  - 日线行情（东方财富源）
  - 财务指标
  - 概念成分股
"""

from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from stock_review_system.config import DB_PATH
from stock_review_system.warehouse import WarehouseDB


class AKShareDataFetcher:
    """AKShare 数据拉取器（免费）"""

    def __init__(self):
        if not HAS_AKSHARE:
            raise ImportError("akshare 未安装: pip install akshare")
        self.db = WarehouseDB(str(DB_PATH))

    # ---------- 行情数据 ----------

    def fetch_daily_bar(self, stock_code: str,
                        start: str = None, end: str = None) -> List[Dict]:
        """
        拉取单只股票日线数据
        stock_code: 6位代码，如 300001
        返回: [{trade_date, open, high, low, close, volume}, ...]
        """
        if not HAS_AKSHARE:
            return []

        code = stock_code.strip().zfill(6)
        symbol = f"{code}"

        # A股区分交易所
        if code.startswith(("0", "3", "002", "003")):
            symbol = f"sz{code}"
        else:
            symbol = f"sh{code}"

        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily",
                                     start_date=start, end_date=end,
                                     adjust="qfq")
        except Exception:
            return []

        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            trade_date = str(row.get('日期', ''))
            if not trade_date or trade_date == 'NaT':
                continue
            # 转换日期格式 2025-08-20
            try:
                td = datetime.strptime(trade_date, "%Y-%m-%d").strftime("%Y-%m-%d")
            except Exception:
                continue

            records.append({
                'stock_code': code,
                'exchange': 'SZSE' if code.startswith(("0", "3", "002", "003")) else 'SSE',
                'adj_mode': 'qfq',
                'trade_date': td,
                'open': row.get('开盘'),
                'high': row.get('最高'),
                'low': row.get('最低'),
                'close': row.get('收盘'),
                'volume': row.get('成交量'),
            })
        return records

    def fetch_bars_batch(self, stock_codes: List[str],
                         start: str = None, end: str = None,
                         max_workers: int = 8) -> int:
        """
        批量拉取多只股票日线数据
        stock_codes: [code, ...]
        返回: 成功拉取的股票数量
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        success = 0
        total = len(stock_codes)

        def _fetch_one(code):
            try:
                recs = self.fetch_daily_bar(code, start, end)
                for rec in recs:
                    self.db.insert_price(rec)
                return 1 if recs else 0
            except Exception:
                return 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_fetch_one, c): c for c in stock_codes}
            for future in as_completed(futures):
                try:
                    if future.result():
                        success += 1
                except Exception:
                    pass

        print(f"[*] AKShare 拉取完成: {success}/{total} 只成功")
        return success

    # ---------- 全市场股票列表 ----------

    def fetch_stock_list(self) -> List[Tuple[str, str]]:
        """
        获取全市场A股股票代码列表
        返回: [(code, exchange), ...]
        """
        try:
            df = ak.stock_info_a_code_name()
        except Exception:
            return []

        if df is None or df.empty:
            return []

        result = []
        for _, row in df.iterrows():
            code = str(row['code']).strip().zfill(6)
            if code.startswith(("0", "3", "002", "003")):
                ex = 'SZSE'
            elif code.startswith(("6",)):
                ex = 'SSE'
            elif code.startswith(("4", "8")):
                ex = 'BSE'  # 北交所
            else:
                continue
            result.append((code, ex))
        return result

    # ---------- 概念成分股 ----------

    def fetch_concept_stocks(self, concept_name: str) -> List[str]:
        """
        获取指定概念板块的成分股
        concept_name: 概念名称
        """
        try:
            df = ak.stock_board_concept_name_em(symbol=concept_name)
        except Exception:
            return []

        if df is None or df.empty:
            return []

        codes = []
        for _, row in df.iterrows():
            codes.append(str(row['代码']).strip().zfill(6))
        return codes

    # ---------- 市场概貌（每日行情统计）----------

    def fetch_market_summary(self, date: str = None) -> List[Dict]:
        """
        获取当日市场概貌（用于获取全市场行情）
        date: YYYYMMDD
        """
        if not date:
            date = datetime.now().strftime("%Y%m%d")

        try:
            df = ak.stock_zh_a_spot_em()
        except Exception:
            return []

        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            code = str(row.get('代码', '')).strip().zfill(6)
            if not code or code == '0':
                continue
            records.append({
                'stock_code': code,
                'exchange': 'SZSE' if code.startswith(("0", "3", "002", "003")) else 'SSE',
                'adj_mode': 'qfq',
                'trade_date': date,
                'open': row.get('开盘') or row.get('今开'),
                'high': row.get('最高'),
                'low': row.get('最低'),
                'close': row.get('收盘'),
                'volume': row.get('成交量'),
            })
        return records


def init_warehouse_from_akshare(start: str = None, end: str = None,
                                  stock_codes: List[str] = None,
                                  max_workers: int = 8) -> Dict:
    """
    用 AKShare 初始化 warehouse

    stock_codes: 指定股票代码列表，为 None 则拉取全市场
    """
    fetcher = AKShareDataFetcher()

    if end is None:
        end = datetime.now().strftime("%Y%m%d")
    if start is None:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    if stock_codes is None:
        print("[*] 获取全市场股票列表...")
        stock_codes = [c[0] for c in fetcher.fetch_stock_list()]
        print(f"[*] 共 {len(stock_codes)} 只A股")

    success = fetcher.fetch_bars_batch(stock_codes, start, end,
                                        max_workers=max_workers)
    return {'success': success, 'total': len(stock_codes)}
