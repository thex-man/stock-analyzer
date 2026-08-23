# -*- coding: utf-8 -*-
"""
工具函数
"""

from datetime import datetime, timedelta
from typing import List, Optional
import numpy as np


def trading_days_between(start_date: str, end_date: str,
                         calendar: Optional[List[str]] = None) -> List[str]:
    """计算两个日期之间的交易日"""
    if calendar is None:
        # 简化：跳过周末
        days = []
        d = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        while d <= end:
            if d.weekday() < 5:  # Mon-Fri
                days.append(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)
        return days
    return [d for d in calendar if start_date <= d <= end_date]


def normalize_stock_code(code: str, exchange: str) -> str:
    """
    标准化股票代码
    A股: 000001.SZ, 600001.SH
    """
    code = code.strip().zfill(6)
    if exchange.upper() in ("SH", "SS", "SSE"):
        return f"{code}.SH"
    elif exchange.upper() in ("SZ", "SZSE"):
        return f"{code}.SZ"
    elif exchange.upper() in ("BJ", "BSE"):
        return f"{code}.BJ"
    return f"{code}.{exchange.upper()}"


def parse_stock_code(normalized: str) -> tuple:
    """解析标准化代码 -> (code, exchange)"""
    if "." in normalized:
        code, exchange = normalized.rsplit(".", 1)
        return code.lstrip("0"), exchange.upper()
    return normalized, "UNKNOWN"


def weighted_score(factors: dict, weights: dict) -> float:
    """加权评分"""
    return sum(factors.get(k, 0) * weights.get(k, 0) for k in weights)


def percentile_rank(values: List[float], score: float) -> float:
    """计算得分在列表中的百分位排名"""
    if not values:
        return 0.5
    sorted_vals = sorted(values)
    rank = sum(1 for v in sorted_vals if v < score)
    return rank / len(sorted_vals)


def format_percent(value: float, decimals: int = 2) -> str:
    """格式化为百分比字符串"""
    return f"{value*100:.{decimals}f}%"


def next_trading_date(date: str, calendar: Optional[List[str]] = None) -> str:
    """获取下一个交易日"""
    if calendar:
        d = datetime.strptime(date, "%Y-%m-%d")
        idx = calendar.index(date) if date in calendar else -1
        if idx >= 0 and idx + 1 < len(calendar):
            return calendar[idx + 1]
    # 简化：跳过周末
    d = datetime.strptime(date, "%Y-%m-%d") + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.strftime("%Y-%m-%d")
