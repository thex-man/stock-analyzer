"""
Sheet5: 每日涨幅>6%但不在当日Top3板块内的个股
==============================================
方案：
  - 问财查询每日涨幅>6%的股票（perpage=1000，全量）
  - 从 Sheet4（每日Top3强势个股）读取当日 Top3 板块成分股代码
  - 用股票代码精确排除 Top3 内的个股
  - 写入 Excel
  - 新增：所属概念列，从 concept_data 读取
"""
import sys
sys.path.insert(0, '.')
from stock_data_source import wencai
import json
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import math
import time
import baostock as bs

CONCEPT_DATA_DIR = r'D:\stock\tool\stock\concept_data'

# ============ 0. 加载概念数据缓存 ============
def load_all_concepts():
    """加载 concept_data 下所有 JSON 文件到内存"""
    print('[*] 加载概念数据到内存...')
    cache = {}
    for fpath in Path(CONCEPT_DATA_DIR).glob('*_concepts.json'):
        code = fpath.stem.replace('_concepts', '')
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            concepts = [c['name'] for c in data.get('concepts', [])]
            cache[code] = concepts
        except Exception:
            cache[code] = []
    print(f'[*] 概念数据加载完毕: {len(cache)} 只股票')
    return cache

concept_cache = load_all_concepts()

def get_concepts(code):
    """根据代码（前6位）从缓存获取概念列表"""
    # 去掉 .SZ / .SH / .BJ 后缀，取前6位
    clean = code.split('.')[0].zfill(6)
    concepts = concept_cache.get(clean, [])
    return '|'.join(concepts) if concepts else ''

# ============ 1. 读取板块历史缓存 ============
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
last_10 = dates_sorted[:10]

# 每天 Top3 板块
daily_top3 = {}
for date in last_10:
    day_results = []
    for sym, info in raw.items():
        name = info.get('name', sym)
        for row in info.get('data', []):
            if row.get('d') == date:
                pct = row.get('p', 0)
                day_results.append((pct, name))
                break
    day_results.sort(reverse=True)
    daily_top3[date] = {name for _, name in day_results[:3]}


# 板块涨跌幅映射
board_pct_map = {}
for date in last_10:
    board_pct_map[date] = {}
    for sym, info in raw.items():
        for row in info.get('data', []):
            if row.get('d') == date:
                board_pct_map[date][info.get('name', sym)] = row.get('p', 0)
                break

def fmt_date(d):
    return f"{d[:4]}-{d[4:6]}-{d[6:]}"

# ============ 2. 从 Sheet4 读取每日 Top3 强势个股代码 ============
def load_top3_codes(wb, target_date_str):
    """从 Sheet4 读取指定日期的 Top3 板块全部强势个股代码"""
    ws = wb['每日Top3强势个股']
    codes = set()
    collecting = False
    for row in ws.iter_rows(values_only=True):
        date_val = row[0]
        stock_cell = row[4]
        if date_val and target_date_str in str(date_val):
            collecting = True
            if stock_cell:
                parts = str(stock_cell).split()
                if len(parts) >= 2:
                    codes.add(parts[1].strip())
        elif collecting:
            if date_val is not None:
                break
            if stock_cell:
                parts = str(stock_cell).split()
                if len(parts) >= 2:
                    codes.add(parts[1].strip())
    return codes

# ============ 3b. 用 baostock 反向查个股所属证监会行业分类 ============
_bs_conn = None

def _bs_login():
    global _bs_conn
    if _bs_conn is None:
        _bs_conn = bs.login()
    return _bs_conn

def lookup_boards_baostock(codes):
    """批量用 baostock 查个股所属行业，返回 {代码: 行业名}"""
    _bs_login()
    result = {}
    for code in codes:
        if code.endswith('.SZ'):
            bs_code = 'sz.' + code.replace('.SZ', '')
        elif code.endswith('.SH'):
            bs_code = 'sh.' + code.replace('.SH', '')
        elif code.endswith('.BJ'):
            bs_code = 'bj.' + code.replace('.BJ', '')
        else:
            continue
        rs = bs.query_stock_industry(code=bs_code)
        while rs.next():
            row = rs.get_row_data()
            industry = row[3] if len(row) > 3 else ''
            if industry:
                result[code] = industry
            break
    return result


# ============ 3. 问财查询每日涨幅>6%的个股（全量 perpage=1000）============
def fetch_gainers(date):
    """查询指定日期涨幅>6%的股票，返回 (code, name, pct, board) 列表"""
    ds = fmt_date(date)
    query = f'{ds}涨幅超过6%的股票'

    result = wencai(query, perpage=1000)
    df = result.get('datas')
    if df is None or df.empty:
        return []

    gainers = []
    for _, r in df.iterrows():
        pct = r.get('涨跌幅:前复权')
        try:
            pct = float(pct)
            if math.isnan(pct):
                continue
            if pct <= 6.0:
                continue
        except (ValueError, TypeError):
            continue

        code = str(r.get('股票代码', '')).strip()
        name = str(r.get('股票简称', '')).strip()
        if not code or not name:
            continue

        board_str = str(r.get('所属板块', '') or r.get('所属概念板块', '-'))
        boards = [b.strip() for b in board_str.split('|') if b.strip() and b != '-']
        board = boards[0] if boards else ''  # 先留空，后续用 baostock 补充

        gainers.append((code, name, round(pct, 2), board))

    return gainers

# ============ 4. 主循环 ============
print('查每日涨幅>6%个股（问财 perpage=1000）...')

# 加载 Excel（用于读取 Sheet4 Top3 个股）
wb_excel = load_workbook('data/板块轮动Top10_v4_含非Top3强势个股.xlsx')

daily_other_stocks = {date: [] for date in last_10}

for date in last_10:
    ds_fmt = fmt_date(date)
    print(f'  {ds_fmt}: 查询中...', end='', flush=True)

    # 读取该日 Top3 个股代码
    top3_codes = load_top3_codes(wb_excel, ds_fmt)
    top3 = daily_top3.get(date, set())
    print(f' Top3板块={top3}', end='', flush=True)

    # 查涨幅>6%
    gainers = fetch_gainers(date)
    print(f' 涨幅>6%共{len(gainers)}只', end='', flush=True)

    # 排除 Top3 个股
    non_top3 = [(code, name, pct, board)
                for code, name, pct, board in gainers
                if code not in top3_codes]

    # 用 baostock 补充缺失的板块
    if non_top3:
        codes_need = [c for c, _, _, b in non_top3 if not b]
        if codes_need:
            board_map = lookup_boards_baostock(codes_need)
            non_top3 = [(code, name, pct, board_map.get(code, board))
                        for code, name, pct, board in non_top3]

    print(f' -> 非Top3 {len(non_top3)}只（排除Top3内{len(gainers)-len(non_top3)}只）')

    daily_other_stocks[date] = non_top3
    time.sleep(2)

bs.logout()

# 排序
for date in last_10:
    daily_other_stocks[date].sort(key=lambda x: -x[2])

# ============ 5. 写入 Excel ============
print('\n写入 Excel...')
out_path = 'data/板块轮动Top10_v4_含非Top3强势个股.xlsx'

if '非Top3板块强势个股' in wb_excel.sheetnames:
    del wb_excel['非Top3板块强势个股']

ws = wb_excel.create_sheet('非Top3板块强势个股')

DAY_COLORS = [
    'D6E4F0', 'EBF5FB', 'D5F5E3', 'FEF9E7', 'FDEDEC',
    'F4ECF7', 'E8F8F5', 'FDF2E9', 'F0F3FF', 'F9EBEA',
]

thin = Side(style='thin', color='CCCCCC')
border = Border(left=thin, right=thin, top=thin, bottom=thin)

# 列定义：用概念替代所属板块，去掉板块类型和所属概念
col_widths = [14, 12, 16, 40, 12, 12]
col_headers = ['日期', '个股代码', '个股简称', '所属概念', '板块涨幅', '个股涨幅']

for i, (w, h) in enumerate(zip(col_widths, col_headers), 1):
    ws.column_dimensions[get_column_letter(i)].width = w
    c = ws.cell(row=1, column=i, value=h)
    c.font = Font(bold=True, color='FFFFFF', size=11)
    c.fill = PatternFill(start_color='2F5496', end_color='2F5496', fill_type='solid')
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = border

ws.freeze_panes = 'A2'

row_num = 2
total_stocks = 0

for day_idx, date in enumerate(reversed(last_10)):
    day_color = DAY_COLORS[day_idx % len(DAY_COLORS)]
    items = daily_other_stocks[date]

    if items:
        for code, name, pct, board in items:
            board_pct = board_pct_map.get(date, {}).get(board, 0)
            concepts = get_concepts(code)  # 新增：读取概念数据
            # 所属板块改为概念数据（板类型不再需要），概念列去掉（与所属板块重复）
            row_data = [
                fmt_date(date), code, name, concepts,
                f'{board_pct:+.2f}%', f'{pct:+.2f}%'
            ]
            for col_i, val in enumerate(row_data, 1):
                c = ws.cell(row=row_num, column=col_i, value=val)
                c.fill = PatternFill(start_color=day_color, end_color=day_color, fill_type='solid')
                c.border = border
                c.alignment = Alignment(horizontal='center', vertical='center')
                if col_i in (5, 6):
                    c.alignment = Alignment(horizontal='right', vertical='center')
                    c.font = Font(bold=True, color='C00000')
                if col_i == 4 and val:  # 所属概念列宽文本
                    c.font = Font(color='1F497D', size=9)
                    c.alignment = Alignment(horizontal='left', vertical='center', wrap_text=True)
            row_num += 1
    else:
        c_date = ws.cell(row=row_num, column=1, value=fmt_date(date))
        c_date.font = Font(bold=True)
        ws.cell(row=row_num, column=3, value='无>6%个股（不在Top3板块）')
        for col_i in range(1, 7):
            ws.cell(row=row_num, column=col_i).fill = PatternFill(start_color=day_color, end_color=day_color, fill_type='solid')
            ws.cell(row=row_num, column=col_i).border = border
        c_date.alignment = Alignment(horizontal='center', vertical='center')
        row_num += 1

    total_stocks += len(items)

wb_excel.save(out_path)
print(f'\n已保存: {out_path}')
print(f'Sheet5 共 {total_stocks} 条（所属板块=概念数据）')
print(f'概念数据来源: {CONCEPT_DATA_DIR}')
