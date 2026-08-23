"""
批量查询baostock K线（多进程版本）
用于Sheet5: 筛选非Top3板块中>6%的个股
"""
import baostock as bs
import pandas as pd
import json
import time
import sys
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict

# ============ 1. 生成全A股代码 ============
def gen_codes():
    codes = []
    for i in range(600000, 604000): codes.append(f'sh.{i}')
    for i in range(688000, 689100): codes.append(f'sh.{i}')
    for i in range(1, 1000): codes.append(f'sz.{i:06d}')
    for i in range(2000, 3000): codes.append(f'sz.00{i}')
    for i in range(300000, 304000): codes.append(f'sz.{i}')
    return codes

# ============ 2. 进程函数 ============
def fetch_batch(codes):
    """每个进程独立login/ logout"""
    results = {}
    try:
        lg = bs.login()
        if lg.error_code != '0':
            return results
        for code in codes:
            try:
                rs = bs.query_history_k_data_plus(
                    code, 'date,close,pctChg',
                    '2026-08-07', '2026-08-20',
                    frequency='d', adjustflag='2')
                if rs.error_code != '0' or not rs.data:
                    continue
                row_map = {}
                for row in rs.data:
                    date_str = row[0].replace('-', '')
                    try:
                        pct = float(row[2]) if row[2] else None
                        if pct is not None:
                            row_map[date_str] = round(pct, 2)
                    except:
                        continue
                if row_map:
                    results[code] = row_map
            except:
                continue
        bs.logout()
    except Exception as e:
        print(f'进程错误: {e}', flush=True)
    return results

# ============ 3. 主流程 ============
if __name__ == '__main__':
    codes = gen_codes()
    print(f'代码总数: {len(codes)}', flush=True)

    # 分成8批
    n = 8
    batch_size = len(codes) // n + 1
    batches = [codes[i:i+batch_size] for i in range(0, len(codes), batch_size)]
    print(f'分成 {len(batches)} 批', flush=True)

    t0 = time.time()
    all_results = {}

    with ProcessPoolExecutor(max_workers=n) as pool:
        futures = {pool.submit(fetch_batch, b): i for i, b in enumerate(batches)}
        for i, future in enumerate(as_completed(futures)):
            result = future.result()
            all_results.update(result)
            elapsed = time.time() - t0
            print(f'批次{i+1}/{len(batches)} 完成, 有效{len(result)}只, 累计{len(all_results)}只, 耗时{elapsed:.0f}s', flush=True)

    # 保存
    out_file = Path('data/bs_kline_20260807_0820.json')
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False)

    total_time = time.time() - t0
    print(f'完成: {len(all_results)}只有效, 总耗时{total_time:.0f}s ({total_time/60:.1f}分钟)', flush=True)
    print(f'已保存: {out_file}', flush=True)
