"""
涨幅≥8%的强势板块成分股交叉分析
================================
找出近10日内单日涨幅≥8%的板块，获取其成分股，
交叉比对同一只股属于几个强势板块，并计算近期最大涨幅。
"""
import sys
sys.path.insert(0, '.')
from stock_data_source import wencai, get_kline
import json
from pathlib import Path
from collections import defaultdict

# ============ 1. 找出涨幅>=8%的板块事件 ============
cache_file = Path('data/board_history_ths/history_20260728_20260820.json')
with open(cache_file, encoding='utf-8') as f:
    raw = json.load(f)

all_dates = set()
for sym, info in raw.items():
    for row in info.get('data', []):
        if row.get('d'):
            all_dates.add(row['d'])

dates_sorted = sorted(all_dates, reverse=True)
last_10 = dates_sorted[:10]

board_events = []
for date in last_10:
    for sym, info in raw.items():
        name = info.get('name', sym)
        btype = info.get('type', '')
        for row in info.get('data', []):
            if row.get('d') == date:
                pct = row.get('p', 0)
                if pct >= 8.0:
                    board_events.append((date, pct, name, btype))
                break

board_events.sort(key=lambda x: (x[0], -x[1]))
print(f"【涨幅≥8%的强势板块事件】共 {len(board_events)} 条")
for e in board_events:
    print(f"  {e[0]}  {e[2]:<16} [{e[3]}]  {e[1]:+.2f}%")

# ============ 2. 获取每个强势板块的成分股 ============
print("\n获取板块成分股...")
board_stocks = {}

for _, _, board_name, btype in board_events:
    if board_name in board_stocks:
        continue
    try:
        result = wencai(f'{board_name}板块有哪些股票')
        df = result.get('datas')
        if df is None or (hasattr(df, 'empty') and df.empty):
            result2 = wencai(f'{board_name}成分股')
            df2 = result2.get('datas')
            if df2 is not None and not (hasattr(df2, 'empty') and df2.empty):
                df = df2
        if df is not None and not (hasattr(df, 'empty') and df.empty):
            stocks = set()
            for _, row in df.iterrows():
                raw_code = str(row.get('股票代码', '')).strip()
                stock_name = str(row.get('股票简称', '')).strip()
                if not raw_code or not stock_name:
                    continue
                # Normalize: '300363.SZ' -> 'sz300363', '603127.SH' -> 'sh603127'
                c = raw_code.lower()
                c = c.replace('.sz', '').replace('.sh', '')
                c = c.replace('.bj', '')  # skip BJ for now
                if c.startswith('6') or c.startswith('9'):
                    code_norm = 'sh' + c
                elif c.startswith('8') or c.startswith('4'):
                    code_norm = 'bj' + c  # BJ not supported by get_kline
                else:
                    code_norm = 'sz' + c
                stocks.add((code_norm, stock_name))
            board_stocks[board_name] = stocks
            print(f"  {board_name}: {len(stocks)} 只")
        else:
            print(f"  {board_name}: 无数据")
    except Exception as e:
        print(f"  {board_name}: 失败 {e}")

# ============ 3. 收集所有成分股并查近10日最大涨幅 ============
all_stocks = set()
for stocks in board_stocks.values():
    all_stocks.update(stocks)

print(f"\n共有 {len(all_stocks)} 只不重复个股，开始查K线...")

end_dt = last_10[0]
start_dt = last_10[-1]

stock_max_gain = {}
for code, name in sorted(all_stocks):
    if code.startswith('bj'):
        stock_max_gain[code] = None
        continue
    try:
        df = get_kline(code, start_dt, end_dt)
        if df is not None and not df.empty:
            close_col = df['close'].astype(float)
            max_close = close_col.max()
            min_close = close_col[close_col > 0].min() if len(close_col[close_col > 0]) > 0 else close_col.min()
            max_gain = (max_close / min_close - 1) * 100 if min_close > 0 else 0
            stock_max_gain[code] = round(max_gain, 2)
        else:
            stock_max_gain[code] = None
    except Exception:
        stock_max_gain[code] = None

# ============ 4. 统计每只股属于几个强势板块 ============
stock_boards = defaultdict(list)
for board_name, stocks in board_stocks.items():
    for code, name in stocks:
        stock_boards[code].append((board_name, name))

multi_board_stocks = {code: boards for code, boards in stock_boards.items() if len(boards) >= 2}
multi_board_stocks_sorted = sorted(multi_board_stocks.items(), key=lambda x: -len(x[1]))

print(f"\n【跨强势板块个股】属于2个及以上强势板块的股票共 {len(multi_board_stocks)} 只：")
for code, boards in multi_board_stocks_sorted:
    board_names = [b[0] for b in boards]
    stock_name = boards[0][1]
    gain = stock_max_gain.get(code)
    gain_str = f"{gain:+.2f}%" if gain is not None else "N/A"
    print(f"  {stock_name:<8} {code}  属: {', '.join(board_names)}  最大涨幅: {gain_str}")

# ============ 5. 完整矩阵表 ============
print(f"\n【完整矩阵表】")
boards_list = [e[2] for e in board_events]
header = f"{'个股':<10}" + "".join([f"{b[:6]:<8}" for b in boards_list]) + f"{'最大涨幅':>10}"
print(header)
print("-" * (10 + 8 * len(boards_list) + 10))

for code, boards in sorted(stock_boards.items(), key=lambda x: -(stock_max_gain.get(x[0]) or 0)):
    stock_name = boards[0][1]
    gain = stock_max_gain.get(code)
    gain_str = f"{gain:+.2f}%" if gain is not None else "      N/A"
    row = f"{stock_name:<10}"
    for b in boards_list:
        board_names_in = [bb[0] for bb in boards]
        row += "    ×    " if b in board_names_in else "         "
    row += f"{gain_str:>10}"
    print(row)

print(f"\n说明：× 表示该股属于该强势板块 | 最大涨幅=近10日最低价→最高价的涨幅")
