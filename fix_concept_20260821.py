# -*- coding: utf-8 -*-
"""
修复脚本 v2：重新拉所有概念板块 8/21 数据 + 重算 8/24 涨幅
================================================
背景：JSON 中：
  - 367 个概念板块有 8/21 数据（部分涨幅错——akshare 8/21 数据源回溯修正）
  - 248 个概念板块完全缺 8/21 数据（akshare 当时拉失败或脚本跳过）
  - 5 个只有到 8/20
  - 3 个只有到 8/21

修复策略：对所有 375 个概念板块都拉 8/21，有就更新，无就插入。
然后对所有有 8/21 的板块，重算 8/24 涨幅。
"""
import json
import sys
from pathlib import Path
import akshare as ak

CACHE_FILE = Path(r'D:\stock\tool\stock\data\board_history_ths\history_20260728_20260824.json')
TARGET_DATE_ISO = '2026-08-21'
TARGET_DATE_SHORT = '20260821'


def main():
    print(f'[*] 修复 8/21 概念板块数据 (含缺失补充)')
    with open(CACHE_FILE, encoding='utf-8') as f:
        raw = json.load(f)

    concept_names = [n for n, info in raw.items() if info.get('type') == '概念']
    print(f'[*] 概念板块: {len(concept_names)}')

    ok = 0
    fail = 0
    inserted = 0   # 新增 8/21
    updated = 0    # 更新 8/21
    pct_fixed = 0  # 重算了 8/24 涨幅
    fail_names = []

    for i, name in enumerate(concept_names, 1):
        try:
            df = ak.stock_board_concept_index_ths(symbol=name, start_date=TARGET_DATE_SHORT, end_date=TARGET_DATE_SHORT)
            if df is None or df.empty:
                fail += 1
                fail_names.append(name)
                continue
            df['_d'] = df['日期'].astype(str)
            row = df[df['_d'] == TARGET_DATE_ISO]
            if row.empty:
                fail += 1
                fail_names.append(name)
                continue

            new_c = float(row['收盘价'].iloc[0])
            new_record = {'d': TARGET_DATE_SHORT, 'c': new_c, 'p': 0}
            data = raw[name].get('data', [])

            # 找 8/21 在 data 中的位置（插入或更新）
            idx_821 = None
            for j, d in enumerate(data):
                if d.get('d') == TARGET_DATE_SHORT:
                    idx_821 = j
                    break

            if idx_821 is None:
                # 插入 8/21 到正确位置（按 d 排序）
                new_record_sorted = new_record
                inserted_idx = len(data)
                for j, d in enumerate(data):
                    if d.get('d', '') > TARGET_DATE_SHORT:
                        inserted_idx = j
                        break
                data.insert(inserted_idx, new_record_sorted)
                idx_821 = inserted_idx
                inserted += 1
            else:
                old_c = float(data[idx_821].get('c', 0))
                if abs(new_c - old_c) < 0.01:
                    pass  # 数据无变化
                else:
                    data[idx_821]['c'] = new_c
                    updated += 1

            # 重算 8/21 当天 p（基于前一个交易日 c）
            if idx_821 > 0:
                prev_c = float(data[idx_821 - 1].get('c', 0))
                if prev_c > 0:
                    data[idx_821]['p'] = round((new_c - prev_c) / prev_c * 100, 4)

            # 重算 8/24 p（基于新的 8/21 c）
            next_824 = None
            for j in range(idx_821 + 1, len(data)):
                if data[j].get('d') == '20260824':
                    next_824 = data[j]
                    break
            if next_824 is not None:
                next_c = float(next_824.get('c', 0))
                if new_c > 0:
                    old_p = float(next_824.get('p', 0))
                    new_p = round((next_c - new_c) / new_c * 100, 4)
                    if abs(old_p - new_p) > 0.001:
                        next_824['p'] = new_p
                        pct_fixed += 1

            ok += 1
            if i % 30 == 0 or i == len(concept_names):
                print(f'  [{i}/{len(concept_names)}] 新增: {inserted}, 更新: {updated}, 重算: {pct_fixed}, 失败: {fail}')

        except Exception as e:
            fail += 1
            fail_names.append(name)

    print(f'\n=== 结果 ===')
    print(f'  OK: {ok}')
    print(f'  新增 8/21 数据: {inserted}')
    print(f'  更新 8/21 c: {updated}')
    print(f'  重算 8/24 p: {pct_fixed}')
    print(f'  失败: {fail}')

    # 保存
    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    # 更新 meta
    meta_file = CACHE_FILE.parent / CACHE_FILE.name.replace('history_', 'meta_')
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump({
            'boards': len(raw),
            'fix_20260821_inserted': inserted,
            'fix_20260821_updated': updated,
            'fix_20260821_failed': fail,
            'fix_20260821_failed_names': fail_names[:30],
        }, f, ensure_ascii=False, indent=2)

    print(f'\n[SAVE] {CACHE_FILE}')
    print(f'[SAVE] {meta_file}')


if __name__ == '__main__':
    main()
