# -*- coding: utf-8 -*-
"""
因子层
=====
每个因子计算函数接收 as_of 参数，保证回测/实盘用同一套代码。

因子评估指标（需在 backtest 层计算）:
  - IC / RankIC
  - 扣成本年化超额
  - 最大回撤
  - 样本外验证 / 滚动窗口验证
"""

from typing import Dict, Optional
from datetime import datetime, date
import numpy as np


# --------------- 业绩反转因子 ---------------

def earnings_reversal_factor(db, stock_code: str, as_of: date) -> Optional[float]:
    """
    业绩反转因子
    - 使用披露时点（非报告期）判断是否提前泄露
    - 计算近几个季度净利润变化率
    """
    reports = db.query_as_of(
        "financial_report", as_of.isoformat(),
        stock_code=stock_code
    )
    if len(reports) < 2:
        return None

    # 按披露日期倒序，取最近两个报告期
    reports.sort(key=lambda x: x['disclosure_date'], reverse=True)
    latest = reports[0]
    previous = reports[1]

    if not latest.get('profit') or not previous.get('profit'):
        return None

    # 净利润变化率（业绩反转 = 之前亏损或下降，当前盈利或上升）
    change = (latest['profit'] - previous['profit']) / abs(previous['profit'])
    return change


def revenue_growth_factor(db, stock_code: str, as_of: date) -> Optional[float]:
    """营收增长率因子"""
    reports = db.query_as_of(
        "financial_report", as_of.isoformat(),
        stock_code=stock_code
    )
    if len(reports) < 2:
        return None

    reports.sort(key=lambda x: x['disclosure_date'], reverse=True)
    latest = reports[0]
    previous = reports[1]

    if not latest.get('revenue') or not previous.get('revenue'):
        return None

    growth = (latest['revenue'] - previous['revenue']) / abs(previous['revenue'])
    return growth


# --------------- 热点因子 ---------------

def topic_hotness_factor(db, stock_code: str, as_of: date) -> Optional[float]:
    """
    话题热度因子
    - 整合舆情数据、互动问答利好标记次数
    """
    sentiments = db.query_as_of(
        "sentiment_data", as_of.isoformat(),
        stock_code=stock_code
    )
    if not sentiments:
        return None

    # 近期热度加权平均
    hotness_scores = [s['topic_hotness'] for s in sentiments if s.get('topic_hotness')]
    if not hotness_scores:
        return None

    return np.mean(hotness_scores)


def sentiment_momentum_factor(db, stock_code: str, as_of: date,
                              lookback_days: int = 5) -> Optional[float]:
    """舆情动量因子（近N日舆情变化率）"""
    sentiments = db.query_as_of(
        "sentiment_data", as_of.isoformat(),
        stock_code=stock_code
    )
    if not sentiments or len(sentiments) < 2:
        return None

    # 过滤出 lookback_days 内的数据
    cutoff = (datetime.fromisoformat(as_of.isoformat()) -
              datetime.timedelta(days=lookback_days)).date().isoformat()

    recent = [s for s in sentiments if s['trade_date'] >= cutoff]
    if len(recent) < 2:
        return None

    recent.sort(key=lambda x: x['trade_date'])
    first = recent[0]['sentiment_score'] or 0
    last = recent[-1]['sentiment_score'] or 0

    if first == 0:
        return None
    return (last - first) / abs(first)


# --------------- 产业链因子 ---------------

def industry_correlation_factor(stock_code: str, concept: str,
                                industry_stocks: Dict[str, list]) -> float:
    """
    产业链关联因子
    - 计算个股与概念板块的关联度
    """
    if concept not in industry_stocks:
        return 0.0

    related = industry_stocks[concept]
    return 1.0 if stock_code in related else 0.0


# --------------- 资金流因子 ---------------

def money_flow_factor(db, stock_code: str, as_of: date,
                      days: int = 5) -> Optional[float]:
    """
    资金流因子
    - 近N日主力资金净流入率
    """
    prices = db.query_as_of(
        "price_history", as_of.isoformat(),
        stock_code=stock_code
    )
    if not prices or len(prices) < days:
        return None

    cutoff = (datetime.fromisoformat(as_of.isoformat()) -
              datetime.timedelta(days=days)).date().isoformat()

    recent = [p for p in prices if p['trade_date'] >= cutoff]
    if not recent:
        return None

    # 简单估算：使用成交量变化率作为资金流代理指标
    recent.sort(key=lambda x: x['trade_date'])
    first_vol = recent[0].get('volume') or 0
    last_vol = recent[-1].get('volume') or 0

    if first_vol == 0:
        return None
    return (last_vol - first_vol) / first_vol
