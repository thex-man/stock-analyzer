# -*- coding: utf-8 -*-
"""
引擎层
=====
信号 → 打分 → 排序 → 决策建议

决策粒度：板块内选活跃股
  - 板块维度：每个概念/产业链选出当日强势板块
  - 个股维度：在板块内按信号分排序，选活跃股（成交量/涨幅/动量综合）

as_of 作为一等参数，回测和实盘走同一条代码路径。
"""

from typing import List, Dict, Optional, Tuple
from datetime import date, datetime, timedelta
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from stock_review_system.config import DEFAULT_N_STOCKS, DEFAULT_HOLDING_PERIOD
from stock_review_system.signals import combined_signal


def get_active_stocks_in_sector(db, sector_stocks: List[str], as_of: date,
                                 lookback_days: int = 5,
                                 top_n: int = 10) -> List[str]:
    """
    从板块内筛选活跃股
    活跃股定义：近N日成交量放大 + 涨幅为正 + 波动率稳定
    """
    stock_activity = []

    for code in sector_stocks:
        prices = db.query_as_of(
            "price_history", as_of.isoformat(), stock_code=code
        )
        if not prices or len(prices) < lookback_days:
            continue

        # 过滤停牌股
        snapshots = db.query_as_of(
            "stock_snapshot", as_of.isoformat(), stock_code=code
        )
        if snapshots and snapshots[0].get('is_suspended'):
            continue

        prices.sort(key=lambda x: x['trade_date'], reverse=True)
        recent = prices[:lookback_days]

        volumes = [p.get('volume', 0) for p in recent if p.get('volume')]
        closes = [p.get('close', 0) for p in recent if p.get('close')]

        if len(volumes) < lookback_days or len(closes) < 2:
            continue

        # 成交量放大率（今日 vs 近N日均值）
        vol_mean = np.mean(volumes[1:]) if len(volumes) > 1 else volumes[0]
        vol_ratio = volumes[0] / vol_mean if vol_mean > 0 else 0

        # 涨幅
        price_change = (closes[0] - closes[-1]) / closes[-1] if closes[-1] > 0 else 0

        # 波动率（标准差/均值）
        if len(closes) > 1 and np.mean(closes) > 0:
            volatility = np.std(closes) / np.mean(closes)
        else:
            volatility = 0

        # 活跃度得分 = 成交量放大 * 涨幅 * 波动率稳定性
        # 波动率稳定性：波动率越低越好，取倒数
        vol_score = min(vol_ratio, 5.0)  # 封顶5倍
        change_score = max(price_change, 0)  # 涨幅只计算正的
        stability_score = max(1 - volatility, 0.1)  # 最低0.1

        activity = vol_score * change_score * stability_score

        stock_activity.append({
            'stock_code': code,
            'activity': activity,
            'vol_ratio': vol_ratio,
            'price_change': price_change,
            'volatility': volatility
        })

    # 按活跃度排序，取top_n
    stock_activity.sort(key=lambda x: x['activity'], reverse=True)
    return stock_activity[:top_n]


def score_stocks(db, stock_codes: List[str], as_of: date,
                 concept: Optional[str] = None,
                 industry_stocks: Optional[Dict[str, list]] = None,
                 weights: Optional[Dict[str, float]] = None,
                 n_stocks: int = DEFAULT_N_STOCKS) -> List[Dict]:
    """
    对股票列表打分排序
    返回: [{stock_code, score, breakdown, signal_types}, ...]
    """
    results = []

    for code in stock_codes:
        # 过滤ST股
        snapshots = db.query_as_of(
            "stock_snapshot", as_of.isoformat(), stock_code=code
        )
        if snapshots and snapshots[0].get('is_st'):
            continue

        scores = combined_signal(
            db, code, as_of, concept, industry_stocks, weights
        )
        results.append({
            'stock_code': code,
            'score': scores['total'],
            'breakdown': scores,
            'holding_period': DEFAULT_HOLDING_PERIOD
        })

    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:n_stocks]


def generate_sector_decision(db, sectors: Dict[str, List[str]], as_of: date,
                               weights: Optional[Dict[str, float]] = None,
                               n_per_sector: int = 5) -> Dict:
    """
    生成板块决策（板块内选活跃股）

    sectors: {板块名: [stock_code, ...], ...}

    返回: {
        date,
        sectors: {
            '板块名': {
                'decision': 'buy'|'hold'|'watch',
                'stocks': [{stock_code, activity, signal_score, breakdown}, ...],
                'avg_activity': float,
                'avg_signal_score': float
            }, ...
        },
        all_stocks: [stock_code, ...],
        sector_scores: {板块名: float, ...}
    }
    """
    sector_results = {}

    for sector_name, stocks in sectors.items():
        # 1. 筛选板块内活跃股
        active = get_active_stocks_in_sector(db, stocks, as_of)
        if not active:
            sector_results[sector_name] = {
                'decision': 'watch',
                'stocks': [],
                'avg_activity': 0.0,
                'avg_signal_score': 0.0,
                'reason': 'no_active_stocks'
            }
            continue

        active_codes = [s['stock_code'] for s in active]

        # 2. 对活跃股打信号分
        scored = score_stocks(db, active_codes, as_of,
                              concept=sector_name,
                              industry_stocks={sector_name: active_codes},
                              weights=weights,
                              n_stocks=n_per_sector)

        if not scored:
            sector_results[sector_name] = {
                'decision': 'watch',
                'stocks': [],
                'avg_activity': np.mean([s['activity'] for s in active]),
                'avg_signal_score': 0.0
            }
            continue

        avg_signal = np.mean([s['score'] for s in scored])
        avg_activity = np.mean([s['activity'] for s in active[:n_per_sector]])

        # 3. 决策判断
        if avg_signal >= 0.4 and avg_activity >= 1.5:
            decision = 'buy'
        elif avg_signal >= 0.2 or avg_activity >= 1.0:
            decision = 'hold'
        else:
            decision = 'watch'

        sector_results[sector_name] = {
            'decision': decision,
            'stocks': scored,
            'avg_activity': avg_activity,
            'avg_signal_score': avg_signal
        }

    # 4. 全局排序（按板块平均信号分）
    sector_scores = {
        name: res['avg_signal_score']
        for name, res in sector_results.items()
    }
    sorted_sectors = sorted(
        sector_scores.items(), key=lambda x: x[1], reverse=True
    )

    # 5. 汇总所有推荐股票
    all_stocks = []
    for sector_name, _ in sorted_sectors:
        stocks = sector_results[sector_name]['stocks']
        all_stocks.extend([s['stock_code'] for s in stocks])

    return {
        'date': as_of.isoformat(),
        'sectors': sector_results,
        'sector_scores': sector_scores,
        'sorted_sectors': [s[0] for s in sorted_sectors],
        'all_stocks': all_stocks,
        'total_sectors': len(sectors),
        'active_sectors': sum(
            1 for r in sector_results.values()
            if r['decision'] in ('buy', 'hold')
        )
    }


def generate_decision(db, date: date,
                      concept: Optional[str] = None,
                      industry_stocks: Optional[Dict[str, list]] = None,
                      n_stocks: int = DEFAULT_N_STOCKS,
                      score_thresh: float = 0.0) -> Dict:
    """
    生成决策建议
    返回: {
        date, top_stocks, avg_score, decision
    }
      - decision: 'buy' | 'hold' | 'watch'
    """
    # 获取全市场股票代码（这里简化处理，实际应从数据库查询）
    stock_codes = _get_all_stock_codes(db, date)

    scored = score_stocks(
        db, stock_codes, date,
        concept, industry_stocks,
        n_stocks=n_stocks
    )

    if not scored:
        return {
            'date': date.isoformat(),
            'decision': 'watch',
            'top_stocks': [],
            'avg_score': 0.0,
            'reason': 'no_valid_stocks'
        }

    top = scored[:n_stocks]
    avg_score = sum(s['score'] for s in top) / len(top)

    if avg_score >= 0.5:
        decision = 'buy'
    elif avg_score >= 0.2:
        decision = 'hold'
    else:
        decision = 'watch'

    return {
        'date': date.isoformat(),
        'decision': decision,
        'top_stocks': [s['stock_code'] for s in top],
        'scores': top,
        'avg_score': avg_score,
        'n_stocks': len(top)
    }


def _get_all_stock_codes(db, as_of: date) -> List[str]:
    """获取as_of时点所有有效股票代码"""
    prices = db.query_as_of("price_history", as_of.isoformat())
    codes = sorted(set(p['stock_code'] for p in prices))
    return codes
