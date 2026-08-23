# -*- coding: utf-8 -*-
"""
股票互动问答增量监控器
- 9:00-15:00 每30分钟检查一次增量更新
- 15:00-24:00 18:00 运行一次
- 0:00-9:00 9:00 运行一次
- 利好消息保存到利好消息.xlsx

已迁移至 stock_review_system/data/
"""

import sys
import io
import os
import json
import time
import random
import datetime
from datetime import datetime, timedelta, time as dt_time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 导入爬虫模块的函数
from crawler_hudongyi import (
    crawl_single_stock_interactive,
    get_stock_dict_from_excel,
    save_good_news,
    GOOD_NEWS_FILE,
    DATE_FORMAT,
    MAX_WORKERS,
)

# -------------------------- 配置 --------------------------
STATE_FILE = "stock_interactive_data/crawl_state.json"
CHECK_INTERVAL_MINUTES = 30

# 交易时段
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 0
MARKET_CLOSE_HOUR = 15
MARKET_CLOSE_MINUTE = 0
EVENING_RUN_HOUR = 23
EVENING_RUN_MINUTE = 30
MORNING_RUN_HOUR = 9


# -------------------------- 状态管理 --------------------------
def load_state():
    """加载增量抓取状态"""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_crawl_time": None, "stocks": {}}


def save_state(state):
    """保存增量抓取状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def update_stock_state(state, stock_code, max_date):
    """更新单只股票的状态"""
    if stock_code not in state["stocks"]:
        state["stocks"][stock_code] = {}
    state["stocks"][stock_code]["last_date"] = max_date
    state["stocks"][stock_code]["last_check"] = datetime.now().isoformat()


# -------------------------- 调度计算 --------------------------
def get_next_run_seconds():
    """计算距下一次运行时间的秒数"""
    now = datetime.now()
    current_time = now.time()

    morning_start = dt_time(MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
    market_close = dt_time(MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    evening_run = dt_time(EVENING_RUN_HOUR, EVENING_RUN_MINUTE)

    if current_time < morning_start:
        next_run = now.replace(hour=MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
    elif current_time < market_close:
        minutes_past = (now.hour * 60 + now.minute) % CHECK_INTERVAL_MINUTES
        next_run = now + timedelta(minutes=CHECK_INTERVAL_MINUTES - minutes_past)
        next_run = next_run.replace(second=0, microsecond=0)
    elif current_time < evening_run:
        next_run = now.replace(hour=EVENING_RUN_HOUR, minute=EVENING_RUN_MINUTE, second=0, microsecond=0)
    else:
        next_run = now.replace(hour=MARKET_OPEN_HOUR, minute=0, second=0, microsecond=0)
        next_run += timedelta(days=1)

    delta = (next_run - now).total_seconds()
    print(f"[*] 下次运行时间: {next_run.strftime('%Y-%m-%d %H:%M:%S')}，约 {delta/60:.0f} 分钟后")
    return int(delta)


# -------------------------- 增量检查 --------------------------
def check_and_crawl_incremental():
    """检查并抓取增量更新"""
    print(f"\n{'='*60}")
    print(f"[*] 开始增量检查 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    state = load_state()
    stock_dict = get_stock_dict_from_excel()
    if not stock_dict:
        print("[ERROR] 无法获取股票列表")
        return

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    stocks_to_crawl = []
    for stock_code, stock_name in stock_dict.items():
        last_date = None
        if stock_code in state["stocks"]:
            last_str = state["stocks"][stock_code].get("last_date")
            if last_str:
                try:
                    last_date = datetime.strptime(last_str, DATE_FORMAT)
                except Exception:
                    pass

        if last_date is None or last_date < today:
            stocks_to_crawl.append((stock_code, stock_name))

    print(f"[*] 发现 {len(stocks_to_crawl)} 只股票可能有更新（{len(stock_dict)} 只中）")

    if not stocks_to_crawl:
        print("[*] 无股票需要检查")
        return

    all_new_records = []
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(crawl_single_stock_interactive, code, name): (code, name)
            for code, name in stocks_to_crawl
        }

        for future in as_completed(futures):
            stock_code, stock_name = futures[future]
            try:
                result = future.result()
                if result:
                    new_records = []
                    for record in result:
                        record_date_str = record.get('日期', '')
                        try:
                            record_date = datetime.strptime(record_date_str, DATE_FORMAT)
                        except Exception:
                            record_date = None

                        if record_date and record_date >= today:
                            new_records.append(record)

                    if new_records:
                        all_new_records.extend(new_records)
                        max_date = max(r.get('日期', '') for r in new_records)
                        update_stock_state(state, stock_code, max_date)
                        successful += 1
                        print(f"[+2] {stock_code} {stock_name}: 新增 {len(new_records)} 条")
                    else:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                print(f"[ERROR] {stock_code}: {str(e)[:50]}")

    print(f"\n[*] 检查完成: 成功 {successful}, 失败 {failed}, 新增 {len(all_new_records)} 条")

    state["last_crawl_time"] = datetime.now().isoformat()
    save_state(state)


# -------------------------- 全量初始化 --------------------------
def full_crawl_initial():
    """全量抓取所有股票的近一天消息（仅首次运行时调用）"""
    print(f"\n{'='*60}")
    print(f"[*] 全量初始化抓取 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")

    state = load_state()
    stock_dict = get_stock_dict_from_excel()
    if not stock_dict:
        print("[ERROR] 无法获取股票列表")
        return

    yesterday = (datetime.now() - timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    all_records = []
    successful = 0
    failed = 0

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(crawl_single_stock_interactive, code, name): (code, name)
            for code, name in stock_dict.items()
        }

        for future in as_completed(futures):
            stock_code, stock_name = futures[future]
            try:
                result = future.result()
                if result:
                    new_records = []
                    for record in result:
                        record_date_str = record.get('日期', '')
                        try:
                            record_date = datetime.strptime(record_date_str, DATE_FORMAT)
                        except Exception:
                            record_date = None

                        if record_date and record_date >= yesterday:
                            new_records.append(record)

                    if new_records:
                        all_records.extend(new_records)
                        max_date = max(r.get('日期', '') for r in new_records)
                        update_stock_state(state, stock_code, max_date)
                        successful += 1
                        print(f"[OK] {stock_code} {stock_name}: {len(new_records)} 条")
                    else:
                        failed += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1

    print(f"\n[*] 全量抓取完成: 成功 {successful}, 失败 {failed}, 总计 {len(all_records)} 条")

    state["last_crawl_time"] = datetime.now().isoformat()
    save_state(state)


# -------------------------- 主调度循环 --------------------------
def main():
    print(f"[*] 股票互动问答增量监控器启动")
    print(f"[*] 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    state = load_state()

    if state["last_crawl_time"] is None:
        print("[*] 首次运行，执行全量初始化...")
        full_crawl_initial()
        print("[*] 全量初始化完成，开始增量监控模式")
    else:
        print("[*] 检测到已有抓取记录，直接进入增量模式")

    while True:
        wait_seconds = get_next_run_seconds()
        print(f"[*] 等待 {wait_seconds} 秒...")
        time.sleep(wait_seconds)
        check_and_crawl_incremental()


if __name__ == "__main__":
    main()


class StockMonitor:
    """股票监控器封装类"""

    def __init__(self, state_file: str = STATE_FILE):
        self.state_file = state_file

    def get_state(self):
        return load_state()

    def run_once(self):
        check_and_crawl_incremental()
