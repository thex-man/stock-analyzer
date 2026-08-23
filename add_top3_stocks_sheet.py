"""
在已有Excel中新增一个Sheet：
每天强势板块Top3 + 板块内当日涨幅>8%的个股
==============================================
思路：
  - 每天取涨幅前3的板块
  - 问财查询 "板块名 YYYYMMDD 涨跌幅排序"，返回该日期的历史成分股涨跌幅
  - 筛选>8%的个股，追加到已有Excel
"""
import sys
sys.path.insert(0, '.')
from stock_data_source import wencai
import json
from pathlib import Path
from collections import Counter
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ============ 1. 读取板块历史数据，找每天Top3 ============
cache_files = sorted(Path('data/board_history_ths').glob('history_*.json'))
cache_file = cache_files[-1]
with open(cache_file, encoding='utf-8') as f:
    raw = json.load(f)

all_dates = set()
for sym, info in raw.items():
    for row in info.get('data', []):
        if row.get('d'):
            all_dates.add(row['d'])

dates_sorted = sorted(all_dates, reverse=True)
last_10 = dates_sorted[:10]  # 最新→最旧

daily_top3 = {}
for date in last_10:
    day_results = []
    for sym, info in raw.items():
        name = info.get('name', sym)
        btype = info.get('type', '')
        for row in info.get('data', []):
            if row.get('d') == date:
                pct = row.get('p', 0)
                day_results.append((pct, name, btype))
                break
    day_results.sort(reverse=True)
    daily_top3[date] = day_results[:3]

# ============ 2. 查询每天Top3板块的成分股历史涨跌幅 ============
# 格式: '20260807' -> '2026-08-07'
def fmt_date(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"

# 缓存（同一天同一个板块只查一次）
cache = {}

def get_board_stocks_on_date(board_name, date_str):
    """查询某个板块在某日期的成分股涨跌幅，筛选>8%"""
    key = (board_name, date_str)
    if key in cache:
        return cache[key]

    ds = fmt_date(date_str)
    # 关键：带日期的历史查询
    query = f'{board_name}板块 {ds} 按涨跌幅排序'

    try:
        result = wencai(query)
        df = result.get('datas')
        if df is None or (hasattr(df, 'empty') and df.empty):
            result2 = wencai(f'{board_name}板块成分股')
            df2 = result2.get('datas')
            if df2 is not None and not (hasattr(df2, 'empty') and df2.empty):
                df = df2

        stocks = []
        if df is not None and not (hasattr(df, 'empty') and df.empty):
            for _, row in df.iterrows():
                try:
                    # 历史日期用 涨跌幅:前复权（真实历史前复权涨跌幅）
                    # 最新涨跌幅 字段只对查询当日有效，历史日期应查 涨跌幅:前复权
                    pct = row.get('涨跌幅:前复权') or row.get('最新涨跌幅')
                    if pct is None:
                        continue
                    pct = float(pct)
                    if pct > 8.0:
                        code = str(row.get('股票代码', '')).strip()
                        name = str(row.get('股票简称', '')).strip()
                        if code and name:
                            stocks.append({'code': code, 'name': name, 'change': round(pct, 2)})
                except (ValueError, TypeError):
                    continue
            stocks.sort(key=lambda x: -x['change'])
    except Exception as e:
        print(f"    [WARN] {board_name} {ds}: {e}")
        stocks = []

    cache[key] = stocks
    return stocks

# ============ 3. 收集数据 ============
print("查询每天Top3板块的>8%成分股...")
all_rows = []  # (date, board_pct, board_name, btype, stocks)

for date in last_10:
    ds_fmt = fmt_date(date)
    print(f"\n{date}")
    for board_pct, board_name, btype in daily_top3[date]:
        stocks = get_board_stocks_on_date(board_name, date)
        if stocks:
            print(f"  {board_name}  {board_pct:+.2f}%  → {len(stocks)}只>8%")
        else:
            print(f"  {board_name}  {board_pct:+.2f}%  → 无>8%")
        all_rows.append((date, board_pct, board_name, btype, stocks))

# ============ 4. 写入Excel（新Sheet） ============
wb = load_workbook('data/板块轮动Top10_v2_行业概念分开.xlsx')

# 检查是否已有该sheet，删除重建
if '每日Top3强势个股' in wb.sheetnames:
    del wb['每日Top3强势个股']

ws = wb.create_sheet('每日Top3强势个股')

# DAY_COLORS 已移除，不再涂色

thin = Side(style='thin', color='CCCCCC')
border = Border(left=thin, right=thin, top=thin, bottom=thin)

# 列设置
col_widths = [14, 16, 10, 18, 14, 12]
col_headers = ['日期', '板块', '板块涨幅', '类型', '强势个股', '个股涨幅']
for i, (w, h) in enumerate(zip(col_widths, col_headers), 1):
    ws.column_dimensions[get_column_letter(i)].width = w
    c = ws.cell(row=1, column=i, value=h)
    c.font = Font(bold=True, color='FFFFFF', size=11)
    c.fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = border

ws.freeze_panes = 'A2'

# 按日期从旧到新排列
row_num = 2
for date in(reversed(last_10)):
    day_boards = [(bp, bn, bt, ss) for (d, bp, bn, bt, ss) in all_rows if d == date]

    # 合并日期列的起始行
    date_start_row = row_num

    for board_pct, board_name, btype, stocks in day_boards:
        if stocks:
            # 第一只：日期+板块+板块涨幅+类型+个股信息 写同一行
            c_date = ws.cell(row=row_num, column=1, value=fmt_date(date))
            c_board = ws.cell(row=row_num, column=2, value=board_name)
            c_bpct = ws.cell(row=row_num, column=3, value=f"{board_pct:+.2f}%")
            c_btype = ws.cell(row=row_num, column=4, value=btype)
            c_stock = ws.cell(row=row_num, column=5, value=f"{stocks[0]['name']} {stocks[0]['code']}")
            c_spct = ws.cell(row=row_num, column=6, value=f"{stocks[0]['change']:+.2f}%")

            for c in [c_date, c_board, c_bpct, c_btype, c_stock, c_spct]:
                c.border = border
                c.alignment = Alignment(horizontal='center', vertical='center')
            c_bpct.alignment = Alignment(horizontal='right', vertical='center')
            c_spct.alignment = Alignment(horizontal='right', vertical='center')
            c_spct.font = Font(bold=True, color='C00000')

            # 后续同板块个股：日期/板块/涨幅/类型合并列，继续填
            for i in range(1, len(stocks)):
                row_num += 1
                # 合并前4列（日期+板块+板块涨幅+类型），保留个股信息列
                ws.cell(row=row_num, column=1, value='')
                ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=4)
                c_stock = ws.cell(row=row_num, column=5, value=f"{stocks[i]['name']} {stocks[i]['code']}")
                c_spct = ws.cell(row=row_num, column=6, value=f"{stocks[i]['change']:+.2f}%")
                for col_i in range(1, 5):
                    ws.cell(row=row_num, column=col_i).border = border
                for c in [c_stock, c_spct]:
                    c.border = border
                    c.alignment = Alignment(horizontal='center', vertical='center')
                c_spct.alignment = Alignment(horizontal='right', vertical='center')
                c_spct.font = Font(bold=True, color='C00000')
        else:
            # 无>8%个股的板块，也显示一行
            c_date = ws.cell(row=row_num, column=1, value=fmt_date(date))
            c_board = ws.cell(row=row_num, column=2, value=board_name)
            c_bpct = ws.cell(row=row_num, column=3, value=f"{board_pct:+.2f}%")
            c_btype = ws.cell(row=row_num, column=4, value=btype)
            c_stock = ws.cell(row=row_num, column=5, value='—')
            c_spct = ws.cell(row=row_num, column=6, value='—')
            for c in [c_date, c_board, c_bpct, c_btype, c_stock, c_spct]:
                c.border = border
                c.alignment = Alignment(horizontal='center', vertical='center')
            c_bpct.alignment = Alignment(horizontal='right', vertical='center')

        row_num += 1

    # 合并该天的日期列
    if date_start_row < row_num - 1:
        ws.merge_cells(start_row=date_start_row, start_column=1, end_row=row_num - 1, end_column=1)
        merged = ws.cell(row=date_start_row, column=1)
        merged.alignment = Alignment(horizontal='center', vertical='center')
        merged.font = Font(bold=True)

    row_num += 1  # 每天空一行

# ============ 5. 保存 ============
out_path = 'data/板块轮动Top10_v3_含每日Top3强势个股.xlsx'
wb.save(out_path)
print(f"\n已追加Sheet到: {out_path}")

# 统计
total = sum(len(ss) for _, _, _, _, ss in all_rows)
print(f"共 {len(last_10)} 天，{sum(len(daily_top3[d]) for d in last_10)} 个板块，{total} 条强势个股记录")
