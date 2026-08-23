# -*- coding: utf-8 -*-
"""
回测层
=====
评估指标：
  - IC / RankIC
  - 扣成本年化超额收益
  - 最大回撤
  - 夏普比率（可选）

验证方式：
  - 样本外验证（out-of-sample）
  - 滚动窗口验证（rolling window）
"""

from typing import List, Dict, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from stock_review_system.engine import score_stocks
from stock_review_system.config import DEFAULT_HOLDING_PERIOD


class BacktestEngine:
    """回测引擎"""

    def __init__(self, db, start_date: str, end_date: str,
                 initial_capital: float = 1000000.0,
                 commission_rate: float = 0.0003):
        self.db = db
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.trading_days = self._load_trading_days()

    def _load_trading_days(self) -> List[str]:
        """加载交易日历"""
        import csv
        from stock_review_system.config import TRADING_DAYS_FILE

        if not Path(TRADING_DAYS_FILE).exists():
            return []

        days = []
        with open(TRADING_DAYS_FILE, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                days.append(row['trade_date'])
        return sorted(days)

    def _get_trading_dates(self, start: str, end: str) -> List[str]:
        """获取区间内的交易日期"""
        return [d for d in self.trading_days if start <= d <= end]

    def run_backtest(self, strategy_func, n_stocks: int = 20,
                     holding_period: int = DEFAULT_HOLDING_PERIOD) -> Dict:
        """
        运行回测

        strategy_func: (db, date) -> List[stock_code]
        """
        dates = self._get_trading_dates(self.start_date, self.end_date)
        if not dates:
            return {'error': 'no_trading_days'}

        capital = self.initial_capital
        equity_curve = []
        positions = {}
        trade_log = []

        i = 0
        while i < len(dates):
            date = dates[i]

            # 调仓日
            if i % holding_period == 0:
                # 清仓
                for code, pos in list(positions.items()):
                    sell_price = self._get_price(code, date)
                    if sell_price:
                        proceeds = pos['shares'] * sell_price
                        commission = proceeds * self.commission_rate
                        capital += proceeds - commission
                        trade_log.append({
                            'date': date, 'action': 'sell',
                            'code': code, 'price': sell_price,
                            'shares': pos['shares'], 'commission': commission
                        })
                positions.clear()

                # 选股
                signals = strategy_func(self.db, date)
                top_codes = [s['stock_code'] for s in signals[:n_stocks]]

                # 买入
                if top_codes and capital > 0:
                    alloc = capital / len(top_codes)
                    for code in top_codes:
                        buy_price = self._get_price(code, date)
                        if buy_price and buy_price > 0:
                            shares = int(alloc / buy_price / 100) * 100
                            if shares >= 100:
                                cost = shares * buy_price
                                commission = cost * self.commission_rate
                                if cost + commission <= capital:
                                    capital -= (cost + commission)
                                    positions[code] = {'shares': shares, 'entry_price': buy_price}
                                    trade_log.append({
                                        'date': date, 'action': 'buy',
                                        'code': code, 'price': buy_price,
                                        'shares': shares, 'commission': commission
                                    })

            # 记录当日权益
            portfolio_value = capital
            for code, pos in positions.items():
                price = self._get_price(code, date) or pos['entry_price']
                portfolio_value += pos['shares'] * price
            equity_curve.append({'date': date, 'value': portfolio_value})

            i += 1

        return self._calc_metrics(equity_curve, trade_log)

    def _get_price(self, stock_code: str, date: str) -> Optional[float]:
        """获取收盘价"""
        prices = self.db.query_as_of(
            "price_history", date, stock_code=stock_code
        )
        if prices:
            return prices[0].get('close')
        return None

    def _calc_metrics(self, equity_curve: List[Dict],
                     trade_log: List[Dict]) -> Dict:
        """计算评估指标"""
        if not equity_curve:
            return {}

        values = [e['value'] for e in equity_curve]
        dates = [e['date'] for e in equity_curve]

        # 总收益
        total_return = (values[-1] - self.initial_capital) / self.initial_capital

        # 年化收益（假设250交易日）
        n_days = len(dates)
        annual_return = (values[-1] / self.initial_capital) ** (250 / n_days) - 1

        # 最大回撤
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            if dd > max_dd:
                max_dd = dd

        # 扣成本年化超额（对比买入持有基准，这里简化）
        excess_return = total_return  # TODO: 对比基准计算超额

        return {
            'start_date': dates[0],
            'end_date': dates[-1],
            'initial_capital': self.initial_capital,
            'final_value': values[-1],
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_dd,
            'n_trades': len(trade_log),
            'equity_curve': equity_curve,
            'trade_log': trade_log[-50:]  # 最近50条交易记录
        }

    def calc_ic_rankic(self, signals: List[Dict], future_returns: List[float],
                       period: int = 5) -> Dict[str, float]:
        """
        计算 IC（信息系数）和 RankIC

        signals: [{stock_code, score}, ...]
        future_returns: 对应股票的未来N日收益
        """
        if len(signals) != len(future_returns) or len(signals) < 3:
            return {'ic': None, 'rankic': None}

        scores = np.array([s['score'] for s in signals])
        returns = np.array(future_returns)

        # IC: Pearson相关系数
        ic = np.corrcoef(scores, returns)[0, 1]

        # RankIC: Spearman秩相关系数
        from scipy.stats import spearmanr
        rankic, _ = spearmanr(scores, returns)

        return {'ic': ic, 'rankic': rankic}
