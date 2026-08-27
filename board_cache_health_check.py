# -*- coding: utf-8 -*-
"""
Step -0.5 - 板块缓存健康检查（必跑，硬性卡控）
================================================
用途：在跑每日复盘之前，先检查板块缓存是否最新。
      如果缓存不是今天的数据，必须先跑 merge_board_daily.py。

返回状态：
  0 = 缓存是今天的（最新），可继续跑复盘
  1 = 缓存滞后 N 天，提示先跑 Step 0
  2 = 缓存目录不存在或无缓存文件
  3 = 非交易日（周末/节假日），跳过

用法：
  python board_cache_health_check.py              # 检查今天
  python board_cache_health_check.py --date 20260824  # 检查指定日期
  python board_cache_health_check.py --strict     # 严格模式（任何滞后都返回 1）
"""
import argparse
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
import akshare as ak

CACHE_DIR = Path(r'D:\stock\tool\stock\data\board_history_ths')


def get_trade_dates(start='20240101', end=None):
    """获取 A 股交易日历"""
    if end is None:
        end = date.today().strftime('%Y%m%d')
    try:
        df = ak.tool_trade_date_hist_sina()
        df['trade_date'] = df['trade_date'].astype(str)
        return sorted([d.replace('-', '') for d in df['trade_date'].tolist()
                       if start <= d.replace('-', '') <= end])
    except Exception as e:
        print(f'[WARN] 获取交易日历失败: {e}')
        return []


def get_latest_cache_info():
    """读取最新缓存文件的最后日期"""
    if not CACHE_DIR.exists():
        return None, None, 0
    cache_files = sorted(CACHE_DIR.glob('history_*.json'))
    if not cache_files:
        return None, None, 0
    src = cache_files[-1]
    try:
        with open(src, encoding='utf-8') as f:
            raw = json.load(f)
        # 收集所有板块的最新日期，取最大
        last_dates = []
        for info in raw.values():
            if info.get('data'):
                last_dates.append(info['data'][-1].get('d', ''))
        if not last_dates:
            return src, None, 0
        max_date = max(last_dates)
        return src, max_date, len(raw)
    except Exception as e:
        print(f'[ERR] 解析缓存失败: {e}')
        return src, None, 0


def get_target_date(arg_date: str = None) -> str:
    """获取目标日期字符串 YYYYMMDD"""
    if arg_date:
        return arg_date
    return date.today().strftime('%Y%m%d')


def main():
    parser = argparse.ArgumentParser(description='板块缓存健康检查')
    parser.add_argument('--date', help='目标日期 YYYYMMDD（默认今天）')
    parser.add_argument('--strict', action='store_true',
                        help='严格模式：任何滞后都返回非零')
    parser.add_argument('--allow-stale', type=int, default=0,
                        help='允许滞后的天数（默认 0，要求是今天）')
    args = parser.parse_args()

    target_short = get_target_date(args.date)
    target_iso = f'{target_short[:4]}-{target_short[4:6]}-{target_short[6:]}'

    print(f'[CHECK] 目标日期: {target_iso}')
    print(f'[CHECK] 缓存目录: {CACHE_DIR}')

    # 1. 检查缓存目录和文件
    src, last_cache_date, board_count = get_latest_cache_info()
    if src is None:
        print(f'[FAIL] 缓存目录不存在或为空: {CACHE_DIR}')
        print(f'       请先创建缓存（跑 merge_board_daily.py 或手动初始化）')
        return 2

    print(f'[INFO] 最新缓存: {src.name}')
    print(f'[INFO] 缓存板块数: {board_count}')
    print(f'[INFO] 缓存最后日期: {last_cache_date}')

    if last_cache_date is None:
        print(f'[FAIL] 缓存解析失败，看不到任何日期数据')
        return 2

    # 2. 判断目标日期是否是交易日
    target_dt = datetime.strptime(target_short, '%Y%m%d').date()
    trade_dates = get_trade_dates(start='20240101', end=target_short)
    is_trade_day = target_short in trade_dates

    if not is_trade_day:
        # 检查最近一个交易日
        prev_trade_days = [d for d in trade_dates if d <= target_short]
        if prev_trade_days:
            last_trade = prev_trade_days[-1]
            print(f'[SKIP] {target_iso} 不是交易日（最近交易日: {last_trade[:4]}-{last_trade[4:6]}-{last_trade[6:]}）')
            # 如果缓存日期 >= 最近交易日（缓存已经更新到最近交易日之后），认为 OK
            cache_dt = datetime.strptime(last_cache_date, '%Y%m%d').date()
            last_trade_dt = datetime.strptime(last_trade, '%Y%m%d').date()
            if cache_dt >= last_trade_dt:
                print(f'[OK] 缓存覆盖到最近交易日或更新（缓存={last_cache_date}，最近交易日={last_trade}）')
                return 0
            else:
                lag_days = (last_trade_dt - cache_dt).days
                print(f'[WARN] 缓存滞后 {lag_days} 个交易日（缓存={last_cache_date}，最近交易日={last_trade}）')
                if lag_days > args.allow_stale:
                    print(f'[ACTION] 请跑: python merge_board_daily.py')
                    return 1
        else:
            print(f'[WARN] 交易日历为空，无法判断')
        return 3

    # 3. 交易日，比较缓存日期 vs 目标日期
    cache_dt = datetime.strptime(last_cache_date, '%Y%m%d').date()
    lag_days = (target_dt - cache_dt).days

    if lag_days == 0:
        print(f'[OK] 缓存是最新的（{last_cache_date} == {target_short}）')
        return 0
    elif lag_days < 0:
        print(f'[WARN] 缓存日期 {last_cache_date} 晚于目标 {target_short}（异常）')
        return 1
    else:
        print(f'[FAIL] 缓存滞后 {lag_days} 天')
        print(f'       缓存最后日期: {last_cache_date}')
        print(f'       目标日期:     {target_short}')
        print(f'       缺失的日期:   {[(cache_dt + timedelta(days=i+1)).strftime("%Y%m%d") for i in range(lag_days)]}')
        print(f'')
        print(f'[ACTION] 请先跑:')
        print(f'         python merge_board_daily.py --date {target_short}')
        return 1


if __name__ == '__main__':
    sys.exit(main())
