# -*- coding: utf-8 -*-
"""
Tushare 数据接入模块
===================
从 Tushare 拉取行情/财务/概念数据，入库到 warehouse 层

要求:
  export TUSHARE_TOKEN=your_token
  或设置 config.TUSHARE_TOKEN
"""

import os
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import tushare as ts
    HAS_TUSHARE = True
except ImportError:
    HAS_TUSHARE = False

from stock_review_system.config import TUSHARE_TOKEN, DB_PATH
from stock_review_system.warehouse import WarehouseDB


class TushareDataFetcher:
    """Tushare 数据拉取器"""

    def __init__(self, token: Optional[str] = None):
        if not HAS_TUSHARE:
            raise ImportError("tushare 未安装: pip install tushare")
        self.token = token or TUSHARE_TOKEN or os.getenv("TUSHARE_TOKEN", "")
        if not self.token:
            raise ValueError("未设置 TUSHARE_TOKEN，请先设置环境变量或 config.TUSHARE_TOKEN")
        self.pro = ts.ProApi(self.token)
        self.db = WarehouseDB(str(DB_PATH))

    # ---------- 行情数据 ----------

    def fetch_daily_bar(self, stock_code: str, exchange: str,
                        start: str, end: str,
                        adj: str = "qfq") -> List[Dict]:
        """
        拉取日线行情
        stock_code: 证券代码，如 000001
        exchange: 交易所，SSE/SZSE/BSE
        """
        ts_code = self._normalize_ts_code(stock_code, exchange)
        df = self.pro.daily(ts_code=ts_code, start_date=start, end_date=end)
        if df is None or df.empty:
            return []

        records = []
        for _, row in df.iterrows():
            records.append({
                'stock_code': stock_code,
                'exchange': exchange,
                'adj_mode': adj,
                'trade_date': row['trade_date'],
                'open': row.get('open'),
                'high': row.get('high'),
                'low': row.get('low'),
                'close': row.get('close'),
                'volume': row.get('volume'),
            })
        return records

    def fetch_bars_batch(self, stock_codes: List[Tuple[str, str]],
                        start: str, end: str,
                        adj: str = "qfq",
                        max_workers: int = 4) -> int:
        """
        批量拉取多只股票日线数据

        stock_codes: [(code, exchange), ...]
        返回: 成功拉取的股票数量
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        success = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self.fetch_daily_bar, code, ex, start, end, adj): (code, ex)
                for code, ex in stock_codes
            }
            for future in as_completed(futures):
                code, ex = futures[future]
                try:
                    records = future.result()
                    for rec in records:
                        self.db.insert_price(rec)
                    if records:
                        success += 1
                except Exception as e:
                    print(f"[WARN] {code}: {e}")
        return success

    # ---------- 财务数据 ----------

    def fetch_financial_report(self, stock_code: str, exchange: str,
                               year: int, quarter: int) -> List[Dict]:
        """
        拉取财务报告
        report_type: 季报(1)/中报(2)/三季报(3)/年报(4)
        """
        ts_code = self._normalize_ts_code(stock_code, exchange)
        df = self.pro.fina_indicator(ts_code=ts_code, start_date=f"{year}0101",
                                     end_date=f"{year}1231")
        if df is None or df.empty:
            return []

        # 找指定季度的数据
        q_map = {1: '0331', 2: '0630', 3: '0930', 4: '1231'}
        period_end = q_map.get(quarter, '1231')
        period_str = f"{year}{period_end}"

        records = []
        for _, row in df.iterrows():
            if str(row.get('end_date', '')) != period_str:
                continue
            records.append({
                'stock_code': stock_code,
                'exchange': exchange,
                'report_type': str(quarter),
                'report_period': period_str,
                'disclosure_date': str(row.get('ann_date', period_str)),
                'revenue': row.get('revenue'),
                'profit': row.get('profit'),
                'assets': row.get('totalAssets'),
                'liability': row.get('totalLiabilities'),
            })
        return records

    # ---------- 概念成分股 ----------

    def fetch_concept_constituents(self, concept_name: str) -> List[str]:
        """
        拉取概念板块成分股
        concept_name: Tushare 概念代码，如 AI 相关用概念名
        """
        # 先查概念列表找到对应的 concept_id
        try:
            df = self.pro.concept()
        except Exception:
            return []

        if df is None or df.empty:
            return []

        # 模糊匹配概念名
        matched = df[df['name'].str.contains(concept_name, na=False)]
        codes = []
        for _, row in matched.iterrows():
            concept_id = row['code']
            try:
                detail = self.pro.concept_detail(id=concept_id)
                if detail is not None and not detail.empty:
                    for _, d in detail.iterrows():
                        codes.append(d['code'])
            except Exception:
                continue
        return list(set(codes))

    # ---------- 工具 ----------

    def _normalize_ts_code(self, code: str, exchange: str) -> str:
        """code + exchange -> Tushare ts_code 格式"""
        code = code.strip().zfill(6)
        ex_map = {"SSE": "SH", "SZSE": "SZ", "BSE": "BJ"}
        ex = ex_map.get(exchange.upper(), exchange.upper())
        return f"{code}.{ex}"


def init_warehouse_from_tushare(token: str,
                                stock_codes: List[Tuple[str, str]],
                                start: str, end: str,
                                adj: str = "qfq") -> Dict:
    """
    初始化 warehouse：从 Tushare 拉取历史行情

    stock_codes: [(code, exchange), ...]
    返回: {success_count, total_records}
    """
    fetcher = TushareDataFetcher(token=token)
    success = fetcher.fetch_bars_batch(stock_codes, start, end, adj)
    print(f"[OK] 拉取完成: {success}/{len(stock_codes)} 只股票成功")
    return {'success': success, 'total': len(stock_codes)}
