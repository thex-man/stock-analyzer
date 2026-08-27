# -*- coding: utf-8 -*-
"""
Step 0 - 每日合并板块缓存到今日
================================================
读取最新 `data/board_history_ths/history_*.json`，把缺失日期的板块数据补齐。

调用策略：
- 行业：1 次 industry_summary_ths + N 次 industry_index_ths（N=行业数）
  - 默认用 summary_ths 1 次拿当日涨跌幅，再按需逐板块拿点位
  - 90 个行业 ≈ 91 次（安全）
- 概念：只能逐板块调 index_ths（375 次，**超门控**）
  - 默认只补行业；如需概念必须显式 --include-concept 并取得用户确认
- 涨跌幅：行业用 summary_ths 拿；概念用本地算法
  - p = (target_close - prev_close) / prev_close * 100

参数：
  --date YYYYMMDD        目标日期（默认今天）
  --include-concept      也补概念板块（需 100+ 次门控确认）
  --recalc-pct           仅重算涨跌幅 p（不调 akshare，1 次调用也不需要）

使用：
  python merge_board_daily.py                       # 仅补行业
  python merge_board_daily.py --date 20260824       # 指定日期
  python merge_board_daily.py --include-concept     # 行业+概念（需确认）
  python merge_board_daily.py --recalc-pct         # 仅重算涨跌幅
"""
import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path
import akshare as ak

CACHE_DIR = Path(r'D:\stock\tool\stock\data\board_history_ths')


def get_target_date(arg_date: str = None) -> str:
    if arg_date:
        return arg_date
    return date.today().strftime('%Y%m%d')


def get_latest_cache():
    cache_files = sorted(CACHE_DIR.glob('history_*.json'))
    if not cache_files:
        print(f'[ERR] 缓存目录为空: {CACHE_DIR}')
        sys.exit(1)
    src = cache_files[-1]
    print(f'[*] 最新缓存: {src.name}')
    with open(src, encoding='utf-8') as f:
        return src, json.load(f)


def fetch_industry_summary():
    """获取行业涨跌幅，THS 失败时 fallback 到新浪"""
    # 先试 THS
    try:
        print('[1/2] 拉 industry_summary_ths（1 次调用）')
        df = ak.stock_board_industry_summary_ths()
        print(f'  THS 返回 {len(df)} 个行业')
        return dict(zip(df['板块'], df['涨跌幅'].astype(float))), 'ths'
    except Exception as e:
        print(f'  THS 失败: {e}')

    # Fallback 到新浪行业
    print('[1/2] THS 失败，fallback 到新浪行业（1 次调用）')
    df = ak.stock_sector_spot(indicator='行业')
    print(f'  新浪返回 {len(df)} 个行业')
    # 新浪列名：'板块' -> 涨跌幅
    return dict(zip(df['板块'], df['涨跌幅'].astype(float))), 'sina'


def fetch_one_industry_index(symbol: str, target_date_iso: str):
    df = ak.stock_board_industry_index_ths(
        symbol=symbol,
        start_date=target_date_iso.replace('-', ''),
        end_date=target_date_iso.replace('-', '')
    )
    if df is None or df.empty:
        return None
    df['_date_str'] = df['日期'].astype(str)
    row = df[df['_date_str'] == target_date_iso]
    if row.empty:
        return None
    return {
        'd': target_date_iso.replace('-', ''),
        'c': float(row['收盘价'].iloc[0]),
        'p': 0,
    }


def fetch_one_concept_index(symbol: str, target_date_iso: str):
    df = ak.stock_board_concept_index_ths(
        symbol=symbol,
        start_date=target_date_iso.replace('-', ''),
        end_date=target_date_iso.replace('-', '')
    )
    if df is None or df.empty:
        return None
    df['_date_str'] = df['日期'].astype(str)
    row = df[df['_date_str'] == target_date_iso]
    if row.empty:
        return None
    return {
        'd': target_date_iso.replace('-', ''),
        'c': float(row['收盘价'].iloc[0]),
        'p': 0,
    }


def compute_pct(raw: dict, name: str, curr_close: float):
    """Self-compute pct from previous close in cache (never trust summary snapshot)."""
    data = raw.get(name, {}).get('data', [])
    prev_close = float(data[-1]['c']) if data else 0
    if prev_close > 0:
        return round((curr_close - prev_close) / prev_close * 100, 4)
    return None


def update_industries(raw: dict, pct_map: dict, target_date_iso: str, target_date_short: str):
    print(f'[2/2] 遍历行业板块，逐个拉 {target_date_iso} 收盘点位')
    need = [n for n, info in raw.items()
            if info.get('type') == '行业'
            and info.get('data')
            and info['data'][-1].get('d') != target_date_short
            and n in pct_map]
    print(f'  需要补: {len(need)} 个')

    ok, fail = 0, 0
    for i, name in enumerate(need, 1):
        try:
            r = fetch_one_industry_index(name, target_date_iso)
            if r is None:
                fail += 1
                continue
            # pct self-computed from prev close (THS summary can return stale values)
            p = compute_pct(raw, name, r['c'])
            if p is None:
                p = pct_map.get(name, 0)   # last-resort fallback: summary snapshot
                print(f'  [{i}/{len(need)}] {name} [WARN] no prev close, fallback summary pct={p}')
            r['p'] = p
            raw[name]['data'].append(r)
            ok += 1
            if i % 20 == 0 or i == len(need):
                print(f'  [{i}/{len(need)}] 最新 {name}: c={r["c"]:.2f}, p={r["p"]:+.2f}%')
        except Exception as e:
            fail += 1
            print(f'  [{i}/{len(need)}] {name} FAILED: {str(e)[:80]}')

    return ok, fail


def update_concepts(raw: dict, target_date_iso: str, target_date_short: str):
    """补概念板块数据 + 用本地算法算涨跌幅"""
    print(f'[3/3] 概念板块（需门控确认，375 次调用）')
    need = [n for n, info in raw.items()
            if info.get('type') == '概念'
            and info.get('data')
            and info['data'][-1].get('d') != target_date_short]
    print(f'  需要补: {len(need)} 个概念（WARN: 远超 100 次门控）')

    ok, fail = 0, 0
    for i, name in enumerate(need, 1):
        try:
            r = fetch_one_concept_index(name, target_date_iso)
            if r is None:
                fail += 1
                continue
            # 用本地算法算涨幅
            prev_data = raw[name].get('data', [])
            if prev_data:
                prev_close = float(prev_data[-1].get('c', 0))
                if prev_close > 0:
                    r['p'] = round((r['c'] - prev_close) / prev_close * 100, 4)
            raw[name]['data'].append(r)
            ok += 1
            if i % 50 == 0 or i == len(need):
                print(f'  [{i}/{len(need)}] 最新 {name}: c={r["c"]:.2f}, p={r["p"]:+.2f}%')
        except Exception as e:
            fail += 1
            if i <= 3 or i == len(need):
                print(f'  [{i}/{len(need)}] {name} FAILED: {str(e)[:80]}')

    return ok, fail


def recalc_concept_pct(raw: dict, target_date_short: str):
    """仅重算概念板块在目标日期的涨跌幅 (不调 akshare)

    用于修正之前用 0 占位写入的 p 字段。
    """
    print(f'[3/3] 仅重算概念板块涨跌幅 (--recalc-pct, 0 次调用)')
    ok, fail = 0, 0
    for name, info in raw.items():
        if info.get('type') != '概念' or not info.get('data'):
            continue
        data = info['data']
        idx = None
        for i, row in enumerate(data):
            if row.get('d') == target_date_short:
                idx = i
                break
        if idx is None or idx == 0:
            continue
        curr = data[idx]
        prev = data[idx - 1]
        prev_close = float(prev.get('c', 0))
        curr_close = float(curr.get('c', 0))
        if prev_close > 0:
            new_pct = round((curr_close - prev_close) / prev_close * 100, 4)
            old_pct = float(curr.get('p', 0))
            if abs(old_pct - new_pct) > 0.001:
                curr['p'] = new_pct
                ok += 1
        else:
            fail += 1
    print(f'  修正: {ok}, 失败: {fail}')
    return ok, fail


def save_cache(src_file: Path, raw: dict, target_date_short: str, stats: dict):
    old_name = src_file.name
    parts = old_name.replace('history_', '').replace('.json', '').split('_')
    start = parts[0]
    new_name = f'history_{start}_{target_date_short}.json'
    dst = CACHE_DIR / new_name

    with open(dst, 'w', encoding='utf-8') as f:
        json.dump(raw, f, ensure_ascii=False, indent=2)

    meta = CACHE_DIR / new_name.replace('history_', 'meta_')
    with open(meta, 'w', encoding='utf-8') as f:
        json.dump({
            'boards': len(raw),
            **stats,
        }, f, ensure_ascii=False, indent=2)

    print(f'\n[SAVE] {dst}')
    print(f'[SAVE] {meta}')


def check_stale(raw: dict, target_date_short: str) -> bool:
    """Refuse to save if today's pct looks copied from yesterday (THS stale-value bug)."""
    bad = False
    for bt in ('行业', '概念'):
        total = same = 0
        for info in raw.values():
            if info.get('type') != bt or len(info.get('data', [])) < 2:
                continue
            d1, d2 = info['data'][-2], info['data'][-1]
            if d2.get('d') != target_date_short:
                continue
            total += 1
            if abs(float(d1.get('p', 0)) - float(d2.get('p', 0))) < 0.001:
                same += 1
        if total and same / total >= 0.9:
            print(f'  ⚠️⚠️⚠️ {bt}: {same}/{total} pct identical to prev day → STALE DATA, abort save')
            bad = True
    return bad


def main():
    parser = argparse.ArgumentParser(description='每日合并板块缓存')
    parser.add_argument('--date', help='目标日期 YYYYMMDD（默认今天）')
    parser.add_argument('--include-concept', action='store_true',
                        help='也补概念板块（375 次调用，需 100+ 门控确认）')
    parser.add_argument('--recalc-pct', action='store_true',
                        help='仅重算涨跌幅 p（不调 akshare）')
    args = parser.parse_args()

    target_short = get_target_date(args.date)
    target_iso = f'{target_short[:4]}-{target_short[4:6]}-{target_short[6:]}'

    print(f'[*] 目标日期: {target_iso}')
    print(f'[*] 缓存目录: {CACHE_DIR}')

    src_file, raw = get_latest_cache()

    # 行业
    pct_map, src = fetch_industry_summary()
    print(f'  数据来源: {src.upper()}')
    ok_hy, fail_hy = update_industries(raw, pct_map, target_iso, target_short)

    # 概念（可选）
    ok_gn, fail_gn = 0, 0
    if args.recalc_pct:
        ok_gn, fail_gn = recalc_concept_pct(raw, target_short)
    elif args.include_concept:
        ok_gn, fail_gn = update_concepts(raw, target_iso, target_short)
    else:
        n_concept_missing = sum(1 for n, info in raw.items()
                                if info.get('type') == '概念'
                                and info.get('data')
                                and info['data'][-1].get('d') != target_short)
        if n_concept_missing:
            print(f'\n[SKIP] 概念板块 {n_concept_missing} 个未更新（默认不补，需 --include-concept）')

    print(f'\n=== 结果 ===')
    print(f'  行业 OK: {ok_hy}, FAIL: {fail_hy}')
    if args.include_concept or args.recalc_pct:
        print(f'  概念 OK: {ok_gn}, FAIL: {fail_gn}')

    if check_stale(raw, target_short):
        print('\n[ABORT] 疑似 THS 返回旧值，缓存未保存。请稍后重跑。')
        sys.exit(2)

    stats = {
        'industry_ok': ok_hy,
        'industry_fail': fail_hy,
        'concept_ok': ok_gn,
        'concept_fail': fail_gn,
    }
    save_cache(src_file, raw, target_short, stats)
    print(f'\n[DONE] merge_board_daily 完成')


if __name__ == '__main__':
    main()
