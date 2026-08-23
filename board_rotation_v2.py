"""
board_rotation_v2.py
===================
板块轮动分析系统 v2（完整版）

核心功能：
  1. 批量抓取所有行业/概念板块历史K线（同花顺接口）
  2. 计算每日涨跌幅
  3. 轮动分析：近N日累计涨幅、动量、轮动信号、次日预测

用法：
  首次运行（需抓取历史数据，等待约3-5分钟）：
    python board_rotation_v2.py --fetch

  后续运行（用本地缓存数据）：
    python board_rotation_v2.py --analyze

  指定日期范围（默认从7月28日开始）：
    python board_rotation_v2.py --fetch --start 20260728
"""
import os
import json
import time
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd
import akshare as ak

# ============ 路径配置 ============
SCRIPT_DIR = Path(__file__).parent
CACHE_DIR = SCRIPT_DIR / 'data' / 'board_history_ths'
CACHE_DIR.mkdir(parents=True, exist_ok=True)

TODAY_STR = datetime.now().strftime('%Y%m%d')
TODAY_DISPLAY = datetime.now().strftime('%Y-%m-%d')
DEFAULT_START = '20260728'

# ============ 获取板块列表 ============
def get_board_lists():
    """获取所有板块名称和代码"""
    print('  获取板块列表...')
    hy_df = ak.stock_board_industry_name_ths()
    gn_df = ak.stock_board_concept_name_ths()

    hy_boards = [(row['name'], '行业', row['code']) for _, row in hy_df.iterrows()]
    gn_boards = [(row['name'], '概念', row['code']) for _, row in gn_df.iterrows()]

    all_boards = hy_boards + gn_boards
    print(f'  行业板块: {len(hy_boards)} 个, 概念板块: {len(gn_boards)} 个')
    return all_boards

# ============ 批量抓取板块历史 ============
def fetch_board_history(board_name, board_type, code, start_date, end_date, retries=2):
    """抓取单个板块历史K线，返回 (name, type, df) 或 None"""
    func = ak.stock_board_industry_index_ths if board_type == '行业' else ak.stock_board_concept_index_ths

    for attempt in range(retries):
        try:
            df = func(symbol=board_name, start_date=start_date, end_date=end_date)
            if df is not None and not df.empty:
                df = df.copy()
                df['日期'] = pd.to_datetime(df['日期'])
                # 计算每日涨跌幅（基于收盘价）
                df['收盘价'] = pd.to_numeric(df['收盘价'], errors='coerce')
                df['涨跌幅'] = df['收盘价'].pct_change() * 100
                return board_name, board_type, df
        except Exception:
            pass
        time.sleep(0.3)
    return None

def fetch_all_history(start_date, end_date, max_workers=20):
    """
    并行抓取所有板块历史数据
    max_workers: 并发数（不要太高，会被限流）
    """
    boards = get_board_lists()
    cache_file = CACHE_DIR / f'history_{start_date}_{end_date}.json'
    meta_file = CACHE_DIR / f'meta_{start_date}_{end_date}.json'

    # 读缓存
    if cache_file.exists() and meta_file.exists():
        print(f'  [缓存命中] {cache_file.name}')
        with open(cache_file, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        with open(meta_file, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        return raw, meta

    print(f'  开始抓取 {len(boards)} 个板块历史 ({start_date}~{end_date})...')
    print(f'  并发数: {max_workers}')

    results = {}
    done = 0
    failed = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(fetch_board_history, name, btype, code, start_date, end_date): (name, btype)
            for name, btype, code in boards
        }

        for future in as_completed(futures):
            name, btype = futures[future]
            done += 1
            try:
                result = future.result()
                if result:
                    _, _, df = result
                    # 只保留日期和涨跌幅，省存储
                    records = []
                    for _, row in df[['日期', '收盘价', '涨跌幅']].iterrows():
                        if pd.notna(row['涨跌幅']):
                            records.append({
                                'd': row['日期'].strftime('%Y%m%d'),
                                'c': round(row['收盘价'], 2),
                                'p': round(row['涨跌幅'], 4),
                            })
                    results[name] = {'type': btype, 'data': records}
                else:
                    failed.append(name)
            except Exception:
                failed.append(name)

            if done % 50 == 0:
                print(f'  进度: {done}/{len(boards)} (成功:{len(results)}, 失败:{len(failed)})')

    # 保存缓存
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False)
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump({'boards': len(boards), 'success': len(results), 'failed': failed[:20]}, f)

    print(f'  抓取完成: 成功{len(results)}/{len(boards)}, 失败{len(failed)}')
    if failed[:5]:
        print(f'  失败示例: {failed[:5]}')
    return results, {'success': len(results), 'failed': failed}

# ============ 补充当日实时数据 ============
def get_today_str():
    """返回今天的工作日字符串（YYYYMMDD），如果是周末返回None"""
    today = datetime.now()
    if today.weekday() >= 5:  # 周六日不补充
        return None
    return today.strftime('%Y%m%d')

def fetch_sina_realtime_boards():
    """
    从同花顺行业汇总接口（stock_board_industry_summary_ths）获取行业板块实时涨幅，
    从新浪接口（stock_sector_spot）获取概念板块实时涨幅。
    返回 {板块名: 涨跌幅}
    """
    result = {}

    # 1. THS 行业板块实时（包含 能源金属、贵金属 等细分行业）
    try:
        df_ind = ak.stock_board_industry_summary_ths()
        for _, row in df_ind.iterrows():
            name = str(row['板块']).strip()
            pct = row['涨跌幅']
            if name and pct is not None:
                result[name] = float(pct)
        print(f'  THS行业实时: {len(df_ind)} 个板块')
    except Exception as e:
        print(f'  THS行业实时抓取失败: {e}')

    # 2. 新浪概念板块实时
    try:
        df_con = ak.stock_sector_spot(indicator='概念')
        pct_col = next((c for c in df_con.columns if c == '涨跌幅'), None)
        name_col = next((c for c in df_con.columns if c == '板块'), None)
        if pct_col and name_col:
            for _, row in df_con.iterrows():
                name = str(row[name_col]).strip()
                pct = row[pct_col]
                if name and pct and str(pct) not in ('', 'nan'):
                    result[name] = float(pct)
        print(f'  新浪概念实时: {len(df_con)} 个板块')
    except Exception as e:
        print(f'  新浪概念实时抓取失败: {e}')

    return result

def supplement_today_data(raw_data, today_str):
    """
    检查raw_data中每个板块是否有today_str的数据，如果没有则从新浪实时补充。
    返回打补丁后的raw_data（修改原缓存文件）。
    """
    print(f'\n[补充当日数据] {today_str}（从新浪实时接口）')

    sina_data = fetch_sina_realtime_boards()
    print(f'  新浪实时共获取 {len(sina_data)} 个板块')

    patched = 0
    for board_name, info in raw_data.items():
        dates_in_board = {r['d'] for r in info.get('data', [])}
        if today_str in dates_in_board:
            continue  # 已有数据，不需要补充

        # 精确匹配板块名
        pct = sina_data.get(board_name)

        # 尝试模糊匹配（板块名 包含于 新浪名 或 新浪名 包含于 板块名）
        if pct is None:
            for sina_name, sina_pct in sina_data.items():
                if board_name in sina_name or sina_name in board_name:
                    pct = sina_pct
                    break

        if pct is not None:
            # 估算收盘价（用昨收*（1+pct/100））
            last_close = None
            last_pct = None
            for r in sorted(info.get('data', []), key=lambda x: x['d']):
                if r.get('c'):
                    last_close = r['c']
                    last_pct = r.get('p')
                    break
            if last_close:
                close = round(last_close * (1 + pct / 100), 2)
            else:
                close = 0.0

            info['data'].append({'d': today_str, 'c': close, 'p': round(pct, 4)})
            patched += 1

    print(f'  成功补充 {patched} 个板块的当日数据')

    # 重新保存缓存
    cache_files = sorted(Path('data/board_history_ths').glob('history_*.json'))
    cache_file = cache_files[-1]
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(raw_data, f, ensure_ascii=False)
    print(f'  缓存已更新: {cache_file.name}')
    return raw_data


# ============ 轮动分析核心 ============
def analyze_rotation(raw_data, top_n=20):
    """
    raw_data: {板块名: {type, data: [{d, c, p}, ...]}}
    """
    # 收集所有板块每日涨跌幅
    # {date: {board: pct}}
    board_pct = {}  # {board: {date: pct}}

    for board, info in raw_data.items():
        board_pct[board] = {}
        for rec in info['data']:
            board_pct[board][rec['d']] = rec['p']

    # 获取所有日期（排序）
    all_dates = set()
    for bdata in board_pct.values():
        all_dates.update(bdata.keys())
    dates = sorted(all_dates, reverse=True)  # 最新在前

    print(f'\n  数据范围: {dates[-1]} ~ {dates[0]} ({len(dates)}个交易日)')

    results = []
    for board, date_pct in board_pct.items():
        pct_series = [date_pct.get(d, None) for d in dates]

        # 近N日累计涨幅
        n = min(10, len(dates))
        valid = [p for p in pct_series[:n] if p is not None]
        cum_n = round(sum(valid), 2) if valid else None

        # 5日累计
        valid5 = [p for p in pct_series[:5] if p is not None]
        cum5 = round(sum(valid5), 2) if valid5 else None

        # 3日累计
        valid3 = [p for p in pct_series[:3] if p is not None]
        cum3 = round(sum(valid3), 2) if valid3 else None

        # 动量：近3日内上涨天数
        momentum = sum(1 for p in pct_series[:3] if p is not None and p > 0)

        # 最高单日涨幅
        max_pct = round(max((p for p in valid if p is not None), default=0), 2)

        # 今日涨跌幅
        today_pct = pct_series[0] if pct_series else None

        # 昨日
        yesterday_pct = pct_series[1] if len(pct_series) > 1 else None

        # 连续强势天数
        strong_days = 0
        for p in pct_series:
            if p is not None and p > 0:
                strong_days += 1
            else:
                break

        btype = raw_data[board].get('type', '概念')

        results.append({
            '板块': board,
            '类型': btype,
            '今日涨幅': round(today_pct, 2) if today_pct is not None else None,
            '昨日涨幅': round(yesterday_pct, 2) if yesterday_pct is not None else None,
            '近3日累计': cum3,
            '近5日累计': cum5,
            f'近{n}日累计': cum_n,
            '最高单日': max_pct,
            '动量': momentum,
            '连续强势天': strong_days,
        })

    df = pd.DataFrame(results)
    df = df.sort_values(f'近{n}日累计', ascending=False, na_position='last').reset_index(drop=True)
    return df, dates

# ============ 输出分析 ============
def print_analysis(df, dates, top=20):
    n = min(10, len(dates))
    print(f'\n{"=" * 70}')
    print(f'  板块轮动分析 ({dates[-1]} ~ {dates[0]})')
    print(f'{"=" * 70}')

    # ===== 1. 近N日涨幅总榜 =====
    print(f'\n【近{n}日累计涨幅 TOP {top}】\n')
    print(f'  {"排名":<4} {"板块":<20} {"类型":<4} {"今日%":>7} {"近5日":>8} {f"近{n}日":>9} {"动量":>4} {"最高单日":>9}')
    print(f'  {"-" * 65}')
    for i, (_, r) in enumerate(df.head(top).iterrows()):
        today = f'{r["今日涨幅"]:>+6.1f}' if r["今日涨幅"] is not None else '   N/A'
        d5 = f'{r["近5日累计"]:>+7.1f}' if r["近5日累计"] is not None else '   N/A'
        dn = f'{r[f"近{n}日累计"]:>+8.1f}' if r[f"近{n}日累计"] is not None else '   N/A'
        mom = '↑' * int(r['动量']) if r['动量'] else '-'
        mx = f'{r["最高单日"]:>+8.1f}' if r["最高单日"] is not None else '   N/A'
        btype = r['类型'][:2]
        print(f'  {i+1:<4} {r["板块"]:<20} {btype:<4} {today:>7} {d5:>8} {dn:>9} {mom:>4} {mx:>9}')

    # ===== 2. 今日强势但之前低调的（刚启动）=====
    print(f'\n{"=" * 70}')
    print(f'【2. 今日启动（今日涨幅>2%且近5日累计<3%的板块）】\n')
    started = df[(df['今日涨幅'] > 2) & (df['近5日累计'] < 3)].sort_values('今日涨幅', ascending=False).head(8)
    for _, r in started.iterrows():
        print(f'  {r["板块"]:<18} 今日{r["今日涨幅"]:>+5.1f}%  近5日仅{r["近5日累计"]:>+5.1f}%')

    # ===== 3. 连续强势板块（动量极强）=====
    print(f'\n{"=" * 70}')
    print(f'【3. 持续强势（近5日4天以上上涨）】\n')
    持续 = df[(df['动量'] >= 4)].sort_values(f'近{n}日累计', ascending=False).head(8)
    for _, r in 持续.iterrows():
        print(f'  {r["板块"]:<18} 动量{r["动量"]}天  近5日{r["近5日累计"]:>+5.1f}%')

    # ===== 4. 轮动信号：之前强势今日走弱 =====
    print(f'\n{"=" * 70}')
    print(f'【4. 轮动信号：前期强势板块今日走弱（警惕）】\n')
    轮动 = df[(df['近5日累计'] > 3) & (df['今日涨幅'] < -1)].sort_values('今日涨幅').head(8)
    if 轮动.empty:
        print('  暂无明显信号')
    for _, r in 轮动.iterrows():
        print(f'  {r["板块"]:<18} 近5日{r["近5日累计"]:>+5.1f}% → 今日{r["今日涨幅"]:>+5.1f}%')

    # ===== 5. 超跌反弹候选 =====
    print(f'\n{"=" * 70}')
    print(f'【5. 超跌反弹候选（近5日跌幅大但今日抗跌）】\n')
    超跌 = df[(df['近5日累计'] < -3) & (df['今日涨幅'] > 0)].sort_values('今日涨幅', ascending=False).head(8)
    if 超跌.empty:
        print('  暂无明显信号')
    for _, r in 超跌.iterrows():
        print(f'  {r["板块"]:<18} 近5日{r["近5日累计"]:>+5.1f}%  今日{r["今日涨幅"]:>+5.1f}%')

    # ===== 6. 次日轮动预测 =====
    print(f'\n{"=" * 70}')
    print(f'【次日轮动预测】')
    print(f'{"=" * 70}')

    # 综合打分
    candidates = df.copy()
    candidates['轮动得分'] = 0.0

    # 因子1：今日涨幅>0但<3（刚启动，还没加速）
    candidates.loc[(candidates['今日涨幅'] > 0) & (candidates['今日涨幅'] < 3), '轮动得分'] += 3
    candidates.loc[(candidates['今日涨幅'] >= 3) & (candidates['今日涨幅'] < 6), '轮动得分'] += 1
    candidates.loc[candidates['今日涨幅'] <= 0, '轮动得分'] -= 1

    # 因子2：近5日有一定涨幅但不大（不是超跌）
    candidates.loc[(candidates['近5日累计'] > 0) & (candidates['近5日累计'] < 5), '轮动得分'] += 2

    # 因子3：前期跌幅大（超跌反弹概率高）
    candidates.loc[candidates['近5日累计'] < -5, '轮动得分'] += 2

    # 因子4：之前强势今日回调（资金可能流出到其他板块）
    candidates.loc[(candidates['近5日累计'] > 5) & (candidates['今日涨幅'] < 0), '轮动得分'] -= 2

    # 因子5：动量适中（连续2-3天强势，比连续5天安全）
    candidates.loc[(candidates['动量'] >= 2) & (candidates['动量'] <= 3), '轮动得分'] += 1

    top_pred = candidates.nlargest(10, '轮动得分')
    print(f'\n轮动预测 TOP10（综合打分）:\n')
    print(f'  {"排名":<4} {"板块":<18} {"轮动得分":>7} {"今日%":>7} {"近5日%":>8} {"信号":<20}')
    print(f'  {"-" * 65}')
    for i, (_, r) in enumerate(top_pred.iterrows()):
        today = f'{r["今日涨幅"]:>+6.1f}' if r["今日涨幅"] is not None else 'N/A'
        d5 = f'{r["近5日累计"]:>+7.1f}' if r["近5日累计"] is not None else 'N/A'
        score = r['轮动得分']

        # 生成信号标签
        signals = []
        if r['今日涨幅'] > 2 and (r['近5日累计'] is None or r['近5日累计'] < 3):
            signals.append('刚启动')
        if r['近5日累计'] < -3:
            signals.append('超跌')
        if r['动量'] in [2, 3]:
            signals.append('温和动量')
        if r['近5日累计'] > 5 and r['今日涨幅'] < 0:
            signals.append('⚠强势回调')

        sig = ','.join(signals) if signals else '综合优质'
        print(f'  {i+1:<4} {r["板块"]:<18} {score:>7.0f} {today:>7} {d5:>8} {sig:<20}')

    print(f'\n  说明: 轮动得分 > 0 表示次日可能被轮动到的概率较高')
    print(f'  ⚠ 标记的板块为前期强势今日走弱，注意资金可能已撤退')

# ============ 主函数 ============
def main():
    parser = argparse.ArgumentParser(description='板块轮动分析v2')
    parser.add_argument('--fetch', action='store_true', help='抓取所有板块历史数据（首次需等待3-5分钟）')
    parser.add_argument('--analyze', action='store_true', help='分析本地缓存数据')
    parser.add_argument('--start', type=str, default=DEFAULT_START, help=f'开始日期（默认{DEFAULT_START}）')
    parser.add_argument('--end', type=str, default=None, help=f'结束日期（默认今日）')
    parser.add_argument('--top', type=int, default=20, help='展示TOP N（默认20）')
    parser.add_argument('--workers', type=int, default=15, help='并发数（默认15）')
    args = parser.parse_args()

    if args.end is None:
        args.end = datetime.now().strftime('%Y%m%d')

    print(f'\n{"=" * 70}')
    print(f'  板块轮动分析系统 v2  ({datetime.now().strftime("%Y-%m-%d %H:%M")})')
    print(f'{"=" * 70}')

    if args.fetch:
        print(f'\n[抓取板块历史数据] {args.start} ~ {args.end}')
        raw_data, meta = fetch_all_history(args.start, args.end, max_workers=args.workers)

        # 补充当日实时数据（解决THS历史K线延迟问题）
        today_str = get_today_str()
        if today_str:
            raw_data = supplement_today_data(raw_data, today_str)

    if args.analyze or args.fetch:
        cache_file = CACHE_DIR / f'history_{args.start}_{args.end}.json'
        if not cache_file.exists():
            print(f'  缓存文件不存在: {cache_file}')
            print('  请先运行: python board_rotation_v2.py --fetch')
            return

        with open(cache_file, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
        print(f'\n[加载缓存] {len(raw_data)} 个板块')

        df, dates = analyze_rotation(raw_data, top_n=args.top)
        if df is not None and not df.empty:
            print_analysis(df, dates, top=args.top)

            # 保存Excel
            out = CACHE_DIR / f'rotation_v2_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
            df.to_excel(out, index=False)
            print(f'\n  完整数据已保存: {out}')

if __name__ == '__main__':
    main()
