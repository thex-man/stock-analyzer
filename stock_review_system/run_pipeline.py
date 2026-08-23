#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
股票复盘决策系统 - 主入口
=========================

用法:
  # 初始化数据（免费，无需Token）
  python run_pipeline.py --init-data --source akshare --sectors AI,DeepSeek概念

  # 初始化全市场数据（akshare，免费）
  python run_pipeline.py --init-data --source akshare

  # 板块维度复盘
  python run_pipeline.py --date 2025-08-20 --sector-mode --sectors AI,半导体

  # 列出可用板块
  python run_pipeline.py --list-sectors

  # 回测
  python run_pipeline.py --backtest --start 2025-01-01 --end 2025-06-30

  # Web 报告
  streamlit run stock_review_system/reports/app.py
"""

import argparse
import sys
import os
from datetime import datetime, timedelta
from typing import List
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from stock_review_system.config import DB_PATH
from stock_review_system.warehouse import WarehouseDB
from stock_review_system.engine import generate_decision, generate_sector_decision
from stock_review_system.backtest import BacktestEngine
from stock_review_system.reports import generate_markdown_report


# ---------- 概念数据加载 ----------

def load_concept_stocks_from_excel(concept_file: str = None) -> dict:
    """从 all_chixnext_concepts.xlsx 加载概念-股票映射"""
    if concept_file is None:
        concept_file = PROJECT_ROOT / "all_chixnext_concepts.xlsx"
    else:
        concept_file = Path(concept_file)

    import pandas as pd
    df = pd.read_excel(str(concept_file))

    concept_map = {}
    for _, row in df.iterrows():
        code = str(row['code']).strip().zfill(6)
        concepts_str = row['concepts']
        if not isinstance(concepts_str, str):
            continue
        for concept in concepts_str.split(","):
            concept = concept.strip()
            if not concept:
                continue
            if concept not in concept_map:
                concept_map[concept] = []
            concept_map[concept].append(code)
    return concept_map


def match_sectors_to_concepts(sector_names: list, concept_map: dict) -> dict:
    """将用户输入的板块名匹配到实际概念"""
    matched = {}
    for sector in sector_names:
        if sector in concept_map:
            matched[sector] = concept_map[sector]
            continue
        partial = [c for c in concept_map if sector in c]
        if len(partial) == 1:
            matched[sector] = concept_map[partial[0]]
        elif len(partial) > 1:
            best = min(partial, key=len)
            matched[sector] = concept_map[best]
        else:
            matched[sector] = []
    return matched


def load_sector_stocks(db, sector_names: list, as_of_date: str) -> dict:
    """从 all_chixnext_concepts.xlsx 加载各板块的成分股"""
    concept_map = load_concept_stocks_from_excel()
    matched = match_sectors_to_concepts(sector_names, concept_map)

    all_prices = db.query_as_of("price_history", as_of_date)
    valid_codes = set(p['stock_code'] for p in all_prices)

    result = {}
    for sector, codes in matched.items():
        valid = [c for c in codes if c in valid_codes]
        result[sector] = valid
        if not valid:
            print(f"[WARNING] 板块{sector}无有效股票（不在行情数据中）")
    return result


# ---------- 复盘运行 ----------

def run_daily_review(date: str, concept: str = None, industry_stocks: dict = None):
    """运行每日复盘（个股维度）"""
    db = WarehouseDB(str(DB_PATH))

    decision = generate_decision(
        db,
        datetime.strptime(date, "%Y-%m-%d").date(),
        concept=concept,
        industry_stocks=industry_stocks
    )

    print(f"\n{'='*60}")
    print(f"[REVIEW] 复盘报告 {date}")
    print(f"{'='*60}")
    print(f"决策: {decision['decision'].upper()}")
    print(f"平均评分: {decision.get('avg_score', 0):.4f}")
    print(f"持仓数量: {decision.get('n_stocks', 0)}")
    print(f"\n持仓股票:")
    for s in decision.get('scores', [])[:10]:
        print(f"  {s['stock_code']} | {s['score']:.4f}")

    return decision


def run_sector_review(date: str, sectors: list):
    """运行每日复盘（板块维度）"""
    db = WarehouseDB(str(DB_PATH))
    as_of_date = datetime.strptime(date, "%Y-%m-%d").date()

    sector_stocks = load_sector_stocks(db, sectors, date)

    decision = generate_sector_decision(db, sector_stocks, as_of_date)

    print(f"\n{'='*60}")
    print(f"[SECTOR] 板块复盘报告 {date}")
    print(f"{'='*60}")
    print(f"活跃板块数: {decision['active_sectors']} / {decision['total_sectors']}")
    print(f"总持仓股票: {len(decision['all_stocks'])}")

    print(f"\n[SECTOR RANK] 板块排名:")
    for rank, sector_name in enumerate(decision['sorted_sectors'], 1):
        s = decision['sectors'][sector_name]
        print(f"  {rank}. {sector_name} | {s['decision'].upper()} | 信号分: {s['avg_signal_score']:.4f}")

    print(f"\n[DETAIL] 各板块推荐股票:")
    for sector_name, res in decision['sectors'].items():
        print(f"\n  [{sector_name}] {res['decision'].upper()}")
        for stock in res.get('stocks', [])[:5]:
            print(f"    {stock['stock_code']} | 信号分: {stock['score']:.4f}")

    return decision


# ---------- 数据初始化 ----------

def run_init_data(source: str, sector_names: List[str] = None,
                  start: str = None, end: str = None, token: str = None):
    """从指定数据源初始化数据库"""
    if not end:
        end = datetime.now().strftime("%Y%m%d")
    if not start:
        start = (datetime.now() - timedelta(days=365)).strftime("%Y%m%d")

    if source == "akshare":
        from stock_review_system.data import AKShareDataFetcher
        fetcher = AKShareDataFetcher()

        if sector_names:
            concept_map = load_concept_stocks_from_excel()
            matched = match_sectors_to_concepts(sector_names, concept_map)
            all_codes = set()
            for codes in matched.values():
                all_codes.update(codes)
            print(f"[*] 涉及 {len(all_codes)} 只股票")
        else:
            print("[*] 获取全市场股票列表...")
            stock_list = fetcher.fetch_stock_list()
            all_codes = set(c for c, _ in stock_list)
            print(f"[*] 全市场 {len(all_codes)} 只A股")

        print(f"[*] AKShare 拉取 {start} ~ {end}...")
        success = fetcher.fetch_bars_batch(list(all_codes), start, end)
        print(f"[OK] 完成: {success}/{len(all_codes)} 只成功")

    elif source == "tushare":
        from stock_review_system.data import TushareDataFetcher
        if not token:
            token = os.getenv("TUSHARE_TOKEN", "")
            if not token:
                print("错误: tushare模式需要 --token 或设置 TUSHARE_TOKEN")
                sys.exit(1)
        fetcher = TushareDataFetcher(token=token)

        if sector_names:
            concept_map = load_concept_stocks_from_excel()
            matched = match_sectors_to_concepts(sector_names, concept_map)
            all_codes = set()
            for codes in matched.values():
                all_codes.update(codes)
        else:
            all_codes = set()
            for idx in ["000016.SH", "000300.SH", "000905.SH", "000852.SH"]:
                try:
                    df = fetcher.pro.index_weight(limit=500)
                    if df is not None and not df.empty:
                        for _, row in df.iterrows():
                            all_codes.add(row['con_code'])
                except Exception as e:
                    print(f"[WARN] 指数 {idx}: {e}")

        stock_codes = [(code.lstrip("0").zfill(6),
                       "SZSE" if code.startswith(("0", "3", "002", "003")) else "SSE")
                       for code in all_codes]
        print(f"[*] 开始拉取 {len(stock_codes)} 只股票...")
        success = fetcher.fetch_bars_batch(stock_codes, start, end)
        print(f"[OK] 完成: {success}/{len(stock_codes)} 只成功")


# ---------- 回测 ----------

def run_backtest(start_date: str, end_date: str):
    """运行回测"""
    db = WarehouseDB(str(DB_PATH))
    engine = BacktestEngine(db, start_date, end_date)

    def strategy(db, date):
        from stock_review_system.engine import score_stocks
        from stock_review_system.config import DEFAULT_N_STOCKS
        codes = [p['stock_code'] for p in db.query_as_of("price_history", date)]
        return score_stocks(db, codes, date, n_stocks=DEFAULT_N_STOCKS)

    metrics = engine.run_backtest(strategy)

    print(f"\n{'='*60}")
    print(f"[BACKTEST] 回测报告 {start_date} ~ {end_date}")
    print(f"{'='*60}")
    print(f"总收益: {metrics.get('total_return', 0)*100:.2f}%")
    print(f"年化收益: {metrics.get('annual_return', 0)*100:.2f}%")
    print(f"最大回撤: {metrics.get('max_drawdown', 0)*100:.2f}%")
    print(f"交易次数: {metrics.get('n_trades', 0)}")

    return metrics


# ---------- 主入口 ----------

def main():
    parser = argparse.ArgumentParser(description="股票复盘决策系统")
    parser.add_argument("--date", help="复盘日期 (YYYY-MM-DD)")
    parser.add_argument("--concept", help="概念板块（个股维度）")
    parser.add_argument("--sector-mode", action="store_true",
                        help="启用板块维度复盘（板块内选活跃股）")
    parser.add_argument("--sectors", help="板块列表，逗号分隔")
    parser.add_argument("--list-sectors", action="store_true",
                        help="列出所有可用板块")
    parser.add_argument("--init-data", action="store_true",
                        help="从数据源拉取行情初始化数据库")
    parser.add_argument("--source", choices=["akshare", "tushare"], default="akshare",
                        help="数据源（默认akshare，无需token）")
    parser.add_argument("--token", help="Tushare Token（仅tushare模式需要）")
    parser.add_argument("--backtest", action="store_true", help="运行回测")
    parser.add_argument("--start", help="回测开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", help="回测结束日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.list_sectors:
        concept_map = load_concept_stocks_from_excel()
        print(f"\n共 {len(concept_map)} 个概念板块:")
        for i, name in enumerate(sorted(concept_map.keys()), 1):
            count = len(concept_map[name])
            print(f"  {name} ({count}只)")
        return

    if args.init_data:
        sectors = [s.strip() for s in args.sectors.split(",")] if args.sectors else None
        run_init_data(args.source, sectors=sectors, token=args.token)
        return

    if args.backtest:
        if not args.start or not args.end:
            print("错误: 回测需要 --start 和 --end 参数")
            sys.exit(1)
        run_backtest(args.start, args.end)
        return

    if args.sector_mode:
        if not args.sectors:
            print("错误: 板块模式需要 --sectors 参数")
            sys.exit(1)
        sector_list = [s.strip() for s in args.sectors.split(",")]
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        run_sector_review(date_str, sector_list)
        return

    if args.date:
        run_daily_review(args.date, concept=args.concept)
        return

    # 默认运行当日复盘
    today = datetime.now().strftime("%Y-%m-%d")
    run_daily_review(today)


if __name__ == "__main__":
    main()
