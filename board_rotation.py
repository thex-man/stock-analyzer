"""
board_rotation.py
================
板块轮动分析系统

核心思路：
  每天收盘后自动抓取板块数据并存到本地（data/board_history/）
  基于历史数据计算：
    1. 各板块近N日涨幅排名
    2. 板块动量（连续强势天数）
    3. 轮动信号：强势板块筹码松动、低位板块启动
    4. 次日预测：哪些板块可能轮动到

用法：
  抓取今日 + 分析：
    python board_rotation.py --fetch

  仅分析（用本地历史数据）：
    python board_rotation.py --analyze

  分析最近N天：
    python board_rotation.py --analyze --days 10
"""
import os
import json
import argparse
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import akshare as ak

# ============ 路径配置 ============
SCRIPT_DIR = Path(__file__).parent
BOARD_DIR = SCRIPT_DIR / 'data' / 'board_history'
BOARD_DIR.mkdir(parents=True, exist_ok=True)

WC_DIR = r'C:\Users\s5631\AppData\Local\Programs\Python\Python313\Lib\site-packages\pywencai'

TODAY_STR = datetime.now().strftime('%Y%m%d')
TODAY_DISPLAY = datetime.now().strftime('%Y-%m-%d')

# ============ 问财原始接口（绕过库） ============
def wencai_token():
    return subprocess.run(
        ['node', os.path.join(WC_DIR, 'hexin-v.bundle.js')],
        capture_output=True, timeout=10
    ).stdout.decode().strip()

def wencai_raw(query, perpage=50, page=1):
    """返回 (columns, rows) 或 (None, error_msg)"""
    token = wencai_token()
    payload = {
        'add_info': '{"urp":{"scene":1,"company":1,"business":1},"contentType":"json","searchInfo":true}',
        'perpage': str(perpage), 'page': page,
        'source': 'Ths_iwencai_Xuangu',
        'log_info': '{"input_type":"click"}',
        'version': '2.0', 'secondary_intent': 'stock',
        'question': query
    }
    headers = {
        'hexin-v': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
        'Referer': 'http://www.iwencai.com',
    }
    try:
        r = requests.post('http://www.iwencai.com/customized/chart/get-robot-data',
                         json=payload, headers=headers, timeout=15)
        resp = r.json()
        answer = resp['data']['answer'][0]
        txt = answer['txt'][0]
        comp = txt['content']['components'][0]
        comp_data = comp['data']
        cols = [c['index_name'] for c in comp_data['columns']]
        rows = comp_data['datas']
        return cols, rows
    except Exception as e:
        return None, str(e)

# ============ 问财查"近N日涨幅前10概念板块" ============
def wencai_board_history(days, top=20):
    """
    通过问财查询近N日涨幅前10概念板块
    返回 DataFrame: 板块名, 近N日涨幅, 股票代码, 股票名称
    """
    cols, rows = wencai_raw(f'概念板块近{days}日涨幅排行', perpage=top)
    if cols is None:
        return pd.DataFrame(), f'问财失败: {rows}'

    result = []
    for row in rows:
        mapped = {cols[i]: v for i, v in enumerate(row)}
        result.append(mapped)
    df = pd.DataFrame(result)
    return df, None

# ============ 新浪实时板块 ============
def fetch_sina_board(kind='概念', top=175):
    """抓取新浪实时板块数据，返回 DataFrame"""
    try:
        df = ak.stock_sector_spot(indicator=kind)
        name_col = next((c for c in df.columns if '板块' in str(c)), None)
        pct_col = next((c for c in df.columns if '涨跌幅' in str(c) and '_pct' not in c), None)
        if name_col and pct_col:
            df['_pct'] = pd.to_numeric(df[pct_col].astype(str).str.replace('%','').str.replace(',',''), errors='coerce')
            df = df.sort_values('_pct', ascending=False).reset_index(drop=True)
            df = df.head(top)
        return df, None
    except Exception as e:
        return pd.DataFrame(), str(e)

# ============ 保存今日板块数据 ============
def save_today_board(date_str=None):
    """抓取并保存当日板块数据到本地文件"""
    if date_str is None:
        date_str = datetime.now().strftime('%Y%m%d')

    filepath = BOARD_DIR / f'board_{date_str}.json'
    if filepath.exists():
        print(f'  [跳过] {filepath} 已存在')
        return filepath

    result = {}
    for kind in ['概念', '行业']:
        df, err = fetch_sina_board(kind)
        if err:
            print(f'  [{kind}] 抓取失败: {err}')
            continue
        name_col = next((c for c in df.columns if '板块' in str(c)), None)
        pct_col = next((c for c in df.columns if '涨跌幅' in str(c) and '_pct' not in c), None)
        if name_col and pct_col:
            records = []
            for _, row in df.iterrows():
                records.append({
                    '板块': row[name_col],
                    '涨跌幅': row[pct_col],
                    '_pct': row['_pct'],
                })
            result[kind] = records
            print(f'  [{kind}] {len(records)} 条已保存')

    filepath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'  → {filepath}')
    return filepath

# ============ 加载历史板块数据 ============
def load_history_board(days=10):
    """
    加载最近N个交易日的板块数据
    返回 dict: {date_str: {kind: [(板块名, 涨跌幅), ...]}}
    """
    all_files = sorted(BOARD_DIR.glob('board_*.json'), reverse=True)
    history = {}
    count = 0
    for f in all_files:
        if count >= days:
            break
        date_str = f.stem.replace('board_', '')
        try:
            data = json.loads(f.read_text(encoding='utf-8'))
            history[date_str] = {}
            for kind, records in data.items():
                history[date_str][kind] = [(r['板块'], r['_pct']) for r in records]
            count += 1
        except Exception as e:
            print(f'  加载 {f.name} 失败: {e}')
    return history

# ============ 轮动分析核心 ============
def analyze_rotation(history, top_n=20):
    """
    基于历史数据做轮动分析

    输出：
      - 各板块近N日累计涨幅排名
      - 连续强势天数（动量）
      - 轮动信号判断
      - 次日预测
    """
    if not history:
        print('  没有历史数据，请先运行 --fetch 抓取数据')
        return

    # 收集所有板块的每日涨跌幅
    # {板块名: {date: pct}}
    board_pct = {}  # {board: {date: pct}}

    dates = sorted(history.keys(), reverse=True)  # 最新日期排前面
    print(f'\n数据范围: {dates[-1]} ~ {dates[0]} ({len(dates)}个交易日)')

    for date_str, kinds in history.items():
        for kind, records in kinds.items():
            for board_name, pct in records:
                if board_name not in board_pct:
                    board_pct[board_name] = {}
                board_pct[board_name][date_str] = pct

    # 计算各板块近N日累计涨幅
    n = len(dates)
    results = []
    for board, date_pct in board_pct.items():
        pct_series = []
        for d in dates:
            pct_series.append(date_pct.get(d, None))

        # 近N日累计涨幅
        valid = [p for p in pct_series if p is not None]
        if len(valid) < n * 0.5:  # 至少一半天数有数据
            continue
        cum = sum(valid)  # 各日涨跌幅相加 ≈ 累计涨幅%

        # 动量：最近几天持续出现在top前10的次数
        momentum = 0
        for i in range(min(3, len(pct_series))):
            if pct_series[i] is not None and pct_series[i] > 0:
                momentum += 1

        # 最高单日涨幅
        max_pct = max(valid) if valid else 0

        results.append({
            '板块': board,
            f'近{n}日累计%': round(cum, 2),
            '近1日涨幅': pct_series[0] if pct_series else None,
            '近2日涨幅': pct_series[1] if len(pct_series) > 1 else None,
            '近3日涨幅': pct_series[2] if len(pct_series) > 2 else None,
            '最高单日%': round(max_pct, 2),
            '动量分': momentum,
        })

    df = pd.DataFrame(results)
    df = df.sort_values(f'近{n}日累计%', ascending=False).reset_index(drop=True)

    return df, dates

def print_analysis(df, dates, top=20):
    """格式化输出分析结果"""
    n = len(dates)
    print(f'\n{"=" * 65}')
    print(f'  板块轮动分析 ({dates[-1]} ~ {dates[0]})')
    print(f'{"=" * 65}')

    print(f'\n--- 近{n}日累计涨幅 TOP {top} ---\n')
    print(f'  {"板块":<20} {"累计%":>8} {"今日%":>8} {"近2日%":>8} {"动量":>4}  {"最高单日%":>9}')
    print(f'  {"-" * 60}')
    for _, r in df.head(top).iterrows():
        d1 = f'{r["近1日涨幅"]:>+7.1f}' if r['近1日涨幅'] is not None else '   N/A '
        d2 = f'{r["近2日涨幅"]:>+7.1f}' if r['近2日涨幅'] is not None else '   N/A '
        d3 = f'{r["近3日涨幅"]:>+7.1f}' if r['近3日涨幅'] is not None else '   N/A '
        cum = f'{r[f"近{n}日累计%"]:>+7.1f}'
        mom = int(r['动量分'])
        mx = f'{r["最高单日%"]:>+8.1f}'
        mom_bar = '↑' * mom
        print(f'  {r["板块"]:<20} {cum:>8} {d1:>8} {d2:>8} {mom_bar:>4} {mx:>9}')

    # ============ 轮动信号识别 ============
    print(f'\n{"=" * 65}')
    print(f'  轮动信号识别')
    print(f'{"=" * 65}')

    # 信号1：连续强势后今日走弱 → 明日可能轮动到其他板块
    top_boards = df.head(top)['板块'].tolist()

    # 找出"昨日强、但今日回调"的板块
    shift_signal = []
    for _, r in df.iterrows():
        if r['近2日涨幅'] is not None and r['近3日涨幅'] is not None:
            if r['近3日涨幅'] > 1 and r['近2日涨幅'] < 0 and r['近1日涨幅'] < 0:
                shift_signal.append(r)

    if shift_signal:
        print(f'\n  【筹码松动】连续强势后回调，可能资金离场:')
        for r in sorted(shift_signal, key=lambda x: x['近1日涨幅'])[:5]:
            print(f'    {r["板块"]:<18} 3日前+{r["近3日涨幅"]:>5.1f}% → 今日{r["近1日涨幅"]:>+.1f}%')

    # 信号2：低位启动 — 之前没怎么涨，今日开始启动
    bottom启动 = []
    for _, r in df.iterrows():
        d2 = r['近2日涨幅'] or 0
        d3 = r['近3日涨幅'] or 0
        if d2 < 0.5 and d3 < 0.5 and r['近1日涨幅'] > 1.5:
            bottom启动.append(r)

    if bottom启动:
        print(f'\n  【低位启动】之前沉寂、今天突然拉升:')
        for r in sorted(bottom启动, key=lambda x: x['近1日涨幅'], reverse=True)[:5]:
            print(f'    {r["板块"]:<18} 今日 +{r["近1日涨幅"]:>5.1f}%  (近3日仅{d2+d3:+.1f}%)')

    # 信号3：动量最强 — 持续强势
    strong_momentum = df[df['动量分'] >= 2].sort_values(f'近{n}日累计%', ascending=False)
    if not strong_momentum.empty:
        print(f'\n  【持续强势】连续强势板块(动量≥2):')
        for _, r in strong_momentum.head(5).iterrows():
            print(f'    {r["板块"]:<18} 累计+{r[f"近{n}日累计%"]:>5.1f}%  动量{"↑"*int(r["动量分"])}')

    # ============ 次日预测 ============
    print(f'\n{"=" * 65}')
    print(f'  次日轮动预测')
    print(f'{"=" * 65}')

    # 预测逻辑：买入"之前强势但今日回调" + "低位刚启动"
    print(f'''
  预测思路:
  1. 资金从【已高位强势】板块撤出 → 寻找【低位刚启动】板块
  2. 关注：近期超跌但基本面/题材有支撑的板块
  3. 回避：连续强势且今日加速赶顶的板块

  明日值得关注的板块类型:
  · 低位启动: 找{'' if not bottom启动 else bottom启动[0]["板块"]}等
  · 轮动承接: 之前热门但今日回调的板块
  · 超跌反弹: 近期累计跌幅较大、乖离明显的板块
''')

# ============ 主函数 ============
def main():
    parser = argparse.ArgumentParser(description='板块轮动分析')
    parser.add_argument('--fetch', action='store_true', help='抓取今日板块数据并保存')
    parser.add_argument('--analyze', action='store_true', help='分析本地历史数据')
    parser.add_argument('--days', type=int, default=10, help='分析最近N个交易日(默认10)')
    parser.add_argument('--top', type=int, default=20, help='展示TOP N(默认20)')
    args = parser.parse_args()

    print(f'\n{"=" * 65}')
    print(f'  板块轮动分析系统  ({TODAY_DISPLAY})')
    print(f'{"=" * 65}')

    if args.fetch:
        print(f'\n[抓取今日板块数据]')
        save_today_board()
        print('\n抓取完成，现在运行分析...')
        args.analyze = True

    if args.analyze:
        print(f'\n[加载最近{args.days}日历史数据]')
        history = load_history_board(days=args.days)
        print(f'  已加载 {len(history)} 个交易日的板块数据')

        if history:
            df, dates = analyze_rotation(history, top_n=args.top)
            if df is not None and not df.empty:
                print_analysis(df, dates, top=args.top)

                # 保存分析结果
                out_path = BOARD_DIR / f'rotation_analysis_{TODAY_STR}.xlsx'
                df.to_excel(out_path, index=False)
                print(f'\n  分析结果已保存: {out_path}')
        else:
            print('  没有历史数据，请先运行 --fetch')

if __name__ == '__main__':
    main()
