# -*- coding: utf-8 -*-
"""
信号层
======
三大信号定义：
  1. 热点信号（topic_signal）
  2. 产业链信号（industry_signal）
  3. 业绩反转信号（earnings_reversal_signal）

信号输出后可配置阈值，决定是否进入决策加权。
"""

from typing import Dict, Optional, Tuple
from datetime import date
import numpy as np

from stock_review_system.factors import (
    earnings_reversal_factor,
    revenue_growth_factor,
    topic_hotness_factor,
    sentiment_momentum_factor,
    industry_correlation_factor,
    money_flow_factor,
)


def topic_signal(db, stock_code: str, as_of: date,
                 hotness_thresh: float = 0.7,
                 momentum_thresh: float = 0.1) -> Tuple[str, float]:
    """
    热点信号
    返回: (signal_type, score)
      - 'hot_topic': 话题热度超过阈值
      - 'momentum': 舆情动量超过阈值
      - 'none': 无信号
    """
    hotness = topic_hotness_factor(db, stock_code, as_of)
    if hotness and hotness >= hotness_thresh:
        return ('hot_topic', hotness)

    momentum = sentiment_momentum_factor(db, stock_code, as_of)
    if momentum and abs(momentum) >= momentum_thresh:
        return ('momentum', momentum)

    return ('none', 0.0)


def earnings_reversal_signal(db, stock_code: str, as_of: date,
                            earnings_thresh: float = 0.2,
                            revenue_thresh: float = 0.15) -> Tuple[str, float]:
    """
    业绩反转信号
    返回: (signal_type, score)
      - 'earnings_reversal': 净利润反转超过阈值
      - 'revenue_growth': 营收增长超过阈值
      - 'none': 无信号
    """
    earnings = earnings_reversal_factor(db, stock_code, as_of)
    if earnings and abs(earnings) >= earnings_thresh:
        return ('earnings_reversal', earnings)

    revenue = revenue_growth_factor(db, stock_code, as_of)
    if revenue and abs(revenue) >= revenue_thresh:
        return ('revenue_growth', revenue)

    return ('none', 0.0)


def industry_signal(stock_code: str, concept: str,
                    industry_stocks: Dict[str, list],
                    weight: float = 1.0) -> Tuple[str, float]:
    """
    产业链信号
    返回: (signal_type, score)
      - 'industry_related': 个股属于该产业链
    """
    corr = industry_correlation_factor(stock_code, concept, industry_stocks)
    if corr > 0:
        return ('industry_related', corr * weight)
    return ('none', 0.0)


def money_flow_signal(db, stock_code: str, as_of: date,
                      flow_thresh: float = 0.2) -> Tuple[str, float]:
    """
    资金流信号
    返回: (signal_type, score)
    """
    flow = money_flow_factor(db, stock_code, as_of)
    if flow and flow >= flow_thresh:
        return ('money_inflow', flow)
    elif flow and flow <= -flow_thresh:
        return ('money_outflow', flow)
    return ('none', 0.0)


def combined_signal(db, stock_code: str, as_of: date,
                    concept: Optional[str] = None,
                    industry_stocks: Optional[Dict[str, list]] = None,
                    weights: Optional[Dict[str, float]] = None) -> Dict[str, float]:
    """
    综合信号计算
    整合热点、业绩反转、产业链、资金流四个维度
    """
    if weights is None:
        weights = {
            'topic': 0.3,
            'earnings': 0.3,
            'industry': 0.2,
            'money_flow': 0.2
        }

    scores = {}

    # 热点信号
    topic_type, topic_score = topic_signal(db, stock_code, as_of)
    scores['topic'] = topic_score if topic_type != 'none' else 0.0

    # 业绩反转信号
    earnings_type, earnings_score = earnings_reversal_signal(db, stock_code, as_of)
    scores['earnings'] = earnings_score if earnings_type != 'none' else 0.0

    # 产业链信号
    if concept and industry_stocks:
        industry_type, industry_score = industry_signal(
            stock_code, concept, industry_stocks
        )
        scores['industry'] = industry_score if industry_type != 'none' else 0.0
    else:
        scores['industry'] = 0.0

    # 资金流信号
    flow_type, flow_score = money_flow_signal(db, stock_code, as_of)
    scores['money_flow'] = abs(flow_score) if flow_type != 'none' else 0.0

    # 加权总分
    total = sum(scores[k] * weights[k] for k in weights)
    scores['total'] = total

    return scores
