# -*- coding: utf-8 -*-
"""
DB 版 HTML 生成器 - 完全从 DuckDB 读取数据
============================================
DB 先行架构 v1.0

读取表:
  - board_history:  Sheet1/2/3 (行业/概念板块 + 色卡)
  - top3_stocks:    Sheet4 (每日Top3强势个股)
  - non_top3_stocks: Sheet5 (非Top3板块强势个股)
  - macd_signals:    Sheet6/7/8 (MACD数据)

输出:
  - data/每日复盘看板.html
"""
import sys
from pathlib import Path
from datetime import datetime
import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / 'data' / 'stock.duckdb'
OUT_HTML = ROOT / 'data' / '每日复盘看板.html'

N_DAYS = 10  # 最近10个交易日


# ========== 颜色工具 ==========
def get_cell_color(cell_val):
    if cell_val is None:
        return ''
    s = str(cell_val)
    for ch in ['+', '-', '%']:
        s = s.replace(ch, '')
    try:
        pct = float(s)
    except (ValueError, TypeError):
        return ''
    pct_val = pct
    if pct_val >= 7:
        return '#ff6b6b'
    elif pct_val >= 5:
        return '#ffa07a'
    elif pct_val >= 3:
        return '#ffd700'
    elif pct_val >= 1:
        return '#90ee90'
    elif pct_val >= 0:
        return '#f0f0f0'
    else:
        return '#d0d0d0'


def make_cell(v):
    if v is None:
        return {'value': '', 'color': ''}
    return {'value': v, 'color': get_cell_color(v)}


# ========== 数据获取 ==========
def get_connection():
    return duckdb.connect(str(DB_PATH))


def get_recent_trade_dates(n=10):
    """从 board_history 取最近 n 个有数据的交易日（无 API 依赖）"""
    conn = get_connection()
    df = conn.execute("""
        SELECT DISTINCT date FROM board_history
        ORDER BY date DESC LIMIT {n}
    """.format(n=n)).df()
    conn.close()
    dates = [d.date() if hasattr(d, 'date') else d for d in pd.to_datetime(df['date']).dt.date.tolist()]
    return sorted(dates, reverse=True)


def get_board_top10(board_type, n_days=10):
    """从 board_history 获取 Top10（Sheet1/2）"""
    conn = get_connection()
    dates = get_recent_trade_dates(n_days)
    dates_str = [str(d) for d in dates]

    rows = conn.execute("""
        SELECT date, board_name, pct
        FROM board_history
        WHERE board_type = ?
          AND date::VARCHAR IN ({})
        ORDER BY date DESC, pct DESC
    """.format(','.join(["'{}'".format(d) for d in dates_str])),
        [board_type]).df()
    conn.close()

    # 构建 {date_str: [(pct, name), ...]}
    by_date = {}
    for _, row in rows.iterrows():
        d = str(row['date'])[:10]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append((row['pct'], row['board_name']))

    # Top10 per date
    result = {}
    for d, items in by_date.items():
        items.sort(reverse=True)
        result[d] = items[:10]
    return result


def get_top3_stocks(n_days=10):
    """从 top3_stocks 获取 Sheet4 数据"""
    conn = get_connection()
    dates = get_recent_trade_dates(n_days)
    dates_str = [str(d) for d in dates]

    df = conn.execute("""
        SELECT date, board_name, board_type, board_pct, rank_, stock_code, stock_name, stock_pct
        FROM top3_stocks
        WHERE date::VARCHAR IN ({})
        ORDER BY date DESC, rank_, stock_pct DESC
    """.format(','.join(["'{}'".format(d) for d in dates_str]))).df()
    conn.close()

    by_date = {}
    for _, row in df.iterrows():
        d = str(row['date'])[:10]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append({
            'board': row['board_name'],
            'type': row['board_type'],
            'board_pct': row['board_pct'],
            'rank': row['rank_'],
            'code': row['stock_code'],
            'name': row['stock_name'],
            'pct': row['stock_pct'],
        })
    return by_date


def get_non_top3_stocks(n_days=10):
    """从 non_top3_stocks 获取 Sheet5 数据"""
    conn = get_connection()
    dates = get_recent_trade_dates(n_days)
    dates_str = [str(d) for d in dates]

    df = conn.execute("""
        SELECT date, stock_code, stock_name, board_name, board_pct, stock_pct
        FROM non_top3_stocks
        WHERE date::VARCHAR IN ({})
        ORDER BY date DESC, stock_pct DESC
    """.format(','.join(["'{}'".format(d) for d in dates_str]))).df()
    conn.close()

    by_date = {}
    for _, row in df.iterrows():
        d = str(row['date'])[:10]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append({
            'code': row['stock_code'],
            'name': row['stock_name'],
            'board': row['board_name'],
            'board_pct': row['board_pct'],
            'pct': row['stock_pct'],
        })
    return by_date


def get_macd_stocks(signal_type, n_days=10):
    """从 macd_signals 获取 Sheet6/7 数据"""
    conn = get_connection()
    dates = get_recent_trade_dates(n_days)
    dates_str = [str(d) for d in dates]

    df = conn.execute("""
        SELECT date, code, name, macd, gain_pct, score, position, trend, fx, bcie
        FROM macd_signals
        WHERE signal_type = ?
          AND date::VARCHAR IN ({})
        ORDER BY date DESC, score DESC, code
    """.format(','.join(["'{}'".format(d) for d in dates_str])),
        [signal_type]).df()
    conn.close()

    by_date = {}
    for _, row in df.iterrows():
        d = str(row['date'])[:10]
        if d not in by_date:
            by_date[d] = []
        by_date[d].append({
            'code': row['code'],
            'name': row['name'],
            'macd': row['macd'],
            'gain_pct': row['gain_pct'],
            'score': row['score'],
            'position': row['position'],
            'trend': row['trend'],
            'fx': row['fx'],
            'bcie': row['bcie'],
        })
    return by_date


# ========== HTML 构建 ==========
PALETTE = [
    'FF6B6B', 'FF9F43', 'FECA57', '48DBFB', '1DD1A1',
    'A55EEA', 'FD79A8', '00CEC9', '6C5CE7', 'FDCB6E',
    '74B9FF', '55EFC4', 'FF7675', 'D63031', 'E17055',
    '009432', '0652DD', 'FFC312', '1289A7', '12CBC4',
    'EE5A24', 'B53405', '686DE0', '22A6B3', 'F19066',
    'FDA7DF', 'D980FA', 'FAB1A0', '7ED6DF', 'C44569',
    '778BEB', '70A1FF', '7BED9F', 'ECCC68', 'FF6348',
    'A3CB38', '55A3FF', 'FED330', '26DE81', '2BCBBA',
    'EB5D68', '4B7BEC', '45AAF2', 'FCAB10', 'F8B739',
]


def _safe(name):
    return name.replace('(', '').replace(')', '').replace('.', '').replace('/', '')


def build_sheet1_html(label, rows_by_date, all_dates):
    """Sheet1/2: 行业/概念 Top10（原版涂色逻辑：重复板块固定色 + 涨幅合计汇总）"""
    # ---- 统计板块出现次数/涨幅 ----
    board_info = {}  # name -> {'count': N, 'gains': [g1...], 'total': sum}
    for d in all_dates:
        for pct, name in rows_by_date.get(d, []):
            if name not in board_info:
                board_info[name] = {'count': 0, 'gains': []}
            board_info[name]['count'] += 1
            board_info[name]['gains'].append(pct if pct is not None else 0.0)

    # 概念板块：出现次数>1 即涂色（用户 2026-08-27 要求）
    # 行业板块：出现次数>2 且 涨幅>1% 的次数>2
    if label == '概念板块':
        repeat_boards = {
            b: info['count']
            for b, info in board_info.items()
            if info['count'] > 1
        }
    else:
        repeat_boards = {
            b: info['count']
            for b, info in board_info.items()
            if info['count'] > 2 and sum(1 for g in info['gains'] if g > 1.0) > 2
        }
    board_color = {}
    for i, board in enumerate(sorted(repeat_boards)):
        board_color[board] = PALETTE[i % len(PALETTE)]

    # 涨幅合计 >10% 汇总表
    gain_boards = {
        b: sum(info['gains'])
        for b, info in board_info.items()
        if sum(info['gains']) > 10
    }
    gain_sorted = sorted(gain_boards.items(), key=lambda x: -x[1])

    # ---- CSS ----
    css = ''
    for board, color in board_color.items():
        css += f'.board-{_safe(board)} {{ background:#{color} !important; color:#1a1a2e !important; font-weight:600; }}\n'
    for board, total in gain_sorted:
        css += f'.gs-{_safe(board)} {{ background:rgba(255,200,80,0.15) !important; }}\n'

    html = f'<style>{css}</style>'

    # ---- 涨幅合计汇总 ----
    if gain_sorted:
        html += '<div class="repeat-summary" style="margin-bottom:16px;">'
        html += f'<h4 style="color:#93c5fd;margin-bottom:8px;">&#x1F4C8; 涨幅合计 Top（合计>10%，共{len(gain_sorted)}个板块）</h4>'
        html += '<table class="stock-table"><thead><tr><th>板块</th><th>合计涨幅</th><th>上榜次数</th><th>平均涨幅</th></tr></thead><tbody>'
        for board, total in gain_sorted:
            info = board_info[board]
            avg = total / info['count'] if info['count'] else 0
            html += (f'<tr class="gs-{_safe(board)}">'
                     f'<td style="text-align:left;font-weight:600">{board}</td>'
                     f'<td style="text-align:center;font-weight:700;color:#f1c40f">{total:+.2f}%</td>'
                     f'<td style="text-align:center">{info["count"]}</td>'
                     f'<td style="text-align:center;color:#94a3b8">{avg:+.2f}%</td>'
                     f'</tr>')
        html += '</tbody></table></div>'

    # ---- Top10 表格：行=日期，列=第1名..第10名 ----
    html += '<div class="table-wrap"><table class="stock-table">'
    html += '<tr><th>日期</th>' + ''.join(f'<th>第{i}名</th>' for i in range(1, 11)) + '</tr>'
    for d in all_dates:
        items = rows_by_date.get(d, [])
        html += f'<tr><td>{d}</td>'
        for i in range(10):
            if i < len(items):
                pct, name = items[i]
                cls = f' board-{_safe(name)}' if name in board_color else ''
                html += f'<td class="{cls.strip()}">{name} {pct:+.2f}%</td>'
            else:
                html += '<td></td>'
        html += '</tr>'
    html += '</table></div>'
    return html


def build_legend_html(board_history_data, n_days=10):
    """Sheet3: 色卡图例"""
    conn = get_connection()
    dates = get_recent_trade_dates(n_days)
    dates_str = [str(d) for d in dates]

    # Count appearances per board
    df = conn.execute("""
        SELECT board_name, COUNT(*) as cnt,
               SUM(CASE WHEN pct > 1 THEN 1 ELSE 0 END) as strong_cnt
        FROM board_history
        WHERE board_type = '行业'
          AND date::VARCHAR IN ({})
        GROUP BY board_name
        HAVING cnt >= 2 AND strong_cnt >= 1
        ORDER BY cnt DESC, board_name
        LIMIT 20
    """.format(','.join(["'{}'".format(d) for d in dates_str]))).df()

    df2 = conn.execute("""
        SELECT board_name, COUNT(*) as cnt,
               SUM(CASE WHEN pct > 1 THEN 1 ELSE 0 END) as strong_cnt
        FROM board_history
        WHERE board_type = '概念'
          AND date::VARCHAR IN ({})
        GROUP BY board_name
        HAVING cnt >= 2 AND strong_cnt >= 1
        ORDER BY cnt DESC, board_name
        LIMIT 20
    """.format(','.join(["'{}'".format(d) for d in dates_str]))).df()
    conn.close()

    def make_item(name, cnt, color):
        if cnt >= 5:
            color = '#ff6b6b'
        elif cnt >= 3:
            color = '#ffa500'
        elif cnt >= 2:
            color = '#90ee90'
        else:
            color = '#d0d0d0'
        return f'<span class="legend-item" style="background:{color}">{name} {cnt}次</span>'

    html = '<div class="legend-container">'
    html += '<div class="legend-section">'
    html += '<h4>行业板块</h4><div class="legend-items">'
    for _, row in df.iterrows():
        html += make_item(row['board_name'], row['cnt'], '')
    html += '</div></div>'
    html += '<div class="legend-section">'
    html += '<h4>概念板块</h4><div class="legend-items">'
    for _, row in df2.iterrows():
        html += make_item(row['board_name'], row['cnt'], '')
    html += '</div></div></div>'
    return html


def build_top3_html(top3_data, all_dates):
    """Sheet4: 每日Top3强势个股"""
    html = '<div class="filter-bar">'
    html += '<button class="filter-btn active" data-filter="all">全部日期</button>'
    for d in all_dates[:10]:
        html += f'<button class="filter-btn" data-filter="{d}">{d}</button>'
    html += '</div>'

    for d in all_dates:
        items = top3_data.get(d, [])
        active = '' if d == all_dates[0] else ' style="display:none"'
        html += f'<div class="date-section" data-date="{d}"{active}>'
        if not items:
            html += '<p class="empty-msg">暂无数据</p>'
        else:
            html += '<table class="stock-table"><tr>'
            html += '<th>板块</th><th>板块涨幅</th><th>类型</th><th>强势个股</th><th>个股涨幅</th></tr>'
            current_board = None
            for item in items:
                if item['board'] != current_board:
                    current_board = item['board']
                    html += f'<tr class="board-row">'
                    html += f'<td>{item["board"]}</td>'
                    html += f'<td>{item["board_pct"]:+.2f}%</td>'
                    html += f'<td>{item["type"]}</td>'
                    if item['code'] and item['code'] != '-':
                        html += f'<td>{item["name"]} {item["code"]}</td>'
                        html += f'<td>{item["pct"]:+.2f}%</td>'
                    else:
                        html += f'<td>—</td><td>—</td>'
                    html += f'</tr>'
                else:
                    html += f'<tr>'
                    html += f'<td></td><td></td><td></td>'
                    if item['code'] and item['code'] != '-':
                        html += f'<td>{item["name"]} {item["code"]}</td>'
                        html += f'<td>{item["pct"]:+.2f}%</td>'
                    else:
                        html += f'<td>—</td><td>—</td>'
                    html += f'</tr>'
            html += '</table>'
        html += '</div>'
    return html


def build_non_top3_html(non_top3_data, all_dates):
    """Sheet5: 非Top3板块强势个股（涂色：10 日内出现>2 次的个股固定色）"""
    # ---- 统计个股出现次数 ----
    stock_count = {}
    for d in all_dates:
        for item in non_top3_data.get(d, []):
            code = item['code']
            if code:
                stock_count[code] = stock_count.get(code, 0) + 1
    repeat_codes = {c for c, n in stock_count.items() if n > 2}
    # 分配固定色（同 PALETTE）
    code_color = {}
    for i, code in enumerate(sorted(repeat_codes)):
        code_color[code] = PALETTE[i % len(PALETTE)]

    css = ''
    for code, color in code_color.items():
        css += f'.s5-{code} {{ background:#{color} !important; color:#1a1a2e !important; font-weight:600; }}\n'

    summary = ''
    if code_color:
        summary = f'<p style="color:#93c5fd;margin:8px 0;">&#x1F3AF; 10 日内出现>2 次的个股（共 {len(code_color)} 只）：{ "、".join(sorted(code_color)) }</p>'

    html = f'<style>{css}</style>{summary}'
    html += '<div class="filter-bar">'
    html += '<button class="filter-btn active" data-filter="all">全部日期</button>'
    for d in all_dates[:10]:
        html += f'<button class="filter-btn" data-filter="{d}">{d}</button>'
    html += '</div>'

    for d in all_dates:
        items = non_top3_data.get(d, [])
        active = '' if d == all_dates[0] else ' style="display:none"'
        html += f'<div class="date-section" data-date="{d}"{active}>'
        if not items:
            html += '<p class="empty-msg">暂无数据</p>'
        else:
            html += f'<p style="color:#94a3b8;margin-bottom:8px;">共 <b>{len(items)}</b> 只</p>'
            html += '<table class="stock-table"><tr>'
            html += '<th>个股</th><th>所属概念</th><th>板块涨幅</th><th>个股涨幅</th></tr>'
            for item in items:
                cls = f' class="s5-{item["code"]}"' if item['code'] in code_color else ''
                html += f'<tr{cls}>'
                html += f'<td>{item["name"]} {item["code"]}</td>'
                html += f'<td>{item["board"]}</td>'
                html += f'<td>{item["board_pct"]:+.2f}%</td>'
                html += f'<td>{item["pct"]:+.2f}%</td>'
                html += '</tr>'
            html += '</table>'
        html += '</div>'
    return html


def build_macd_html(macd_data, all_dates, label, gain_label):
    """Sheet6/7: MACD强势个股"""
    html = '<div class="filter-bar">'
    html += '<button class="filter-btn active" data-filter="all">全部日期</button>'
    for d in all_dates[:10]:
        html += f'<button class="filter-btn" data-filter="{d}">{d}</button>'
    html += '</div>'

    for d in all_dates:
        items = macd_data.get(d, [])
        active = '' if d == all_dates[0] else ' style="display:none"'
        html += f'<div class="date-section" data-date="{d}"{active}>'
        if not items:
            html += '<p class="empty-msg">暂无数据</p>'
        else:
            html += f'<p style="color:#94a3b8;margin-bottom:8px;">共 <b>{len(items)}</b> 只</p>'
            html += '<table class="stock-table"><tr>'
            html += '<th>#</th><th>代码</th><th>名称</th><th>最新价</th>'
            html += f'<th>MACD</th><th>{gain_label}</th>'
            html += '<th>缠论分数</th><th>位置</th><th>趋势</th><th>分型</th><th>背驰</th></tr>'
            for i, item in enumerate(items, 1):
                html += f'<tr>'
                html += f'<td>{i}</td>'
                html += f'<td>{item["code"]}</td>'
                html += f'<td>{item["name"]}</td>'
                html += f'<td>{item.get("macd","")}</td>'
                html += f'<td>{item["macd"]:.4f}</td>'
                html += f'<td>{item["gain_pct"]:+.2f}%</td>'
                html += f'<td>{item["score"]:+.1f}</td>'
                html += f'<td>{item["position"] or ""}</td>'
                html += f'<td>{item["trend"] or ""}</td>'
                html += f'<td>{item["fx"] or ""}</td>'
                html += f'<td>{item["bcie"] or ""}</td>'
                html += '</tr>'
            html += '</table>'
        html += '</div>'
    return html


def build_macd_recent_html(macd_data, all_dates):
    """Sheet8: MACD 5日>10% 最近10日"""
    total = sum(len(v) for v in macd_data.values())
    html = f'<p style="color:#94a3b8;margin-bottom:8px;">共 <b>{total}</b> 条信号</p>'
    html += '<table class="stock-table"><tr>'
    html += '<th>日期</th><th>代码</th><th>名称</th><th>MACD</th><th>5日涨幅%</th>'
    html += '<th>缠论分数</th><th>趋势</th></tr>'

    for d in all_dates:
        items = macd_data.get(d, [])
        if not items:
            continue
        for item in items:
            color = get_cell_color(str(item.get('gain_pct', 0)))
            html += f'<tr style="background:{color}">'
            html += f'<td>{d}</td>'
            html += f'<td>{item["code"]}</td>'
            html += f'<td>{item["name"]}</td>'
            html += f'<td>{item["macd"]:.4f}</td>'
            html += f'<td>{item["gain_pct"]:+.2f}%</td>'
            html += f'<td>{item["score"]:+.1f}</td>'
            html += f'<td>{item["trend"] or ""}</td>'
            html += '</tr>'
    html += '</table>'
    return html


# ========== 主 HTML 模板 ==========
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日复盘看板</title>
<style>
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ font-family:'Microsoft YaHei', Arial, sans-serif; background:#0f172a; color:#e2e8f0; font-size:14px; }}
.header {{ background:#1e293b; padding:16px 24px; border-bottom:1px solid #334155; display:flex; justify-content:space-between; align-items:center; }}
.header h1 {{ font-size:20px; color:#f1f5f9; }}
.header span {{ color:#94a3b8; font-size:12px; }}
.tabs {{ display:flex; background:#1e293b; border-bottom:1px solid #334155; overflow-x:auto; white-space:nowrap; }}
.tab {{ padding:12px 20px; cursor:pointer; color:#94a3b8; border-bottom:2px solid transparent; font-size:13px; transition:all .2s; }}
.tab:hover {{ color:#e2e8f0; }}
.tab.active {{ color:#38bdf8; border-bottom-color:#38bdf8; }}
.panels {{ padding:20px; }}
.panel {{ display:none; }}
.panel.active {{ display:block; }}
.date-section {{ margin-bottom:24px; background:#1e293b; border-radius:8px; padding:16px; }}
.date-section h3 {{ color:#f1f5f9; margin-bottom:12px; font-size:15px; }}
.date-badge {{ font-size:12px; background:#334155; color:#94a3b8; padding:2px 8px; border-radius:4px; margin-left:8px; }}
.board-list {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(220px,1fr)); gap:8px; }}
.board-item {{ display:flex; align-items:center; padding:8px 12px; border-radius:6px; gap:8px; }}
.board-item .rank {{ font-size:12px; color:#64748b; width:20px; }}
.board-item .board-name {{ flex:1; color:#f1f5f9; font-size:13px; }}
.board-item .board-pct {{ font-size:13px; font-weight:bold; color:#f1f5f9; }}
.legend-container {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; }}
.legend-section h4 {{ color:#38bdf8; margin-bottom:10px; }}
.legend-items {{ display:flex; flex-wrap:wrap; gap:6px; }}
.legend-item {{ padding:4px 10px; border-radius:4px; font-size:12px; color:#0f172a; font-weight:bold; }}
.stock-table {{ width:100%; border-collapse:collapse; margin-top:8px; }}
.stock-table th {{ background:#334155; color:#94a3b8; padding:8px 10px; text-align:left; font-size:12px; }}
.stock-table td {{ padding:8px 10px; border-bottom:1px solid #1e293b; font-size:13px; }}
.stock-table tr:hover {{ background:#263345; }}
.board-row {{ background:#1a2744; }}
.empty-msg {{ color:#64748b; padding:20px; text-align:center; }}
.filter-bar {{ display:flex; gap:6px; flex-wrap:wrap; margin-bottom:16px; }}
.filter-btn {{ padding:6px 14px; background:#334155; border:none; border-radius:6px; color:#94a3b8; cursor:pointer; font-size:12px; }}
.filter-btn:hover, .filter-btn.active {{ background:#38bdf8; color:#0f172a; font-weight:bold; }}
</style>
</head>
<body>
<div class="header">
  <h1>每日复盘看板</h1>
  <span id="update-time"></span>
</div>
<div class="tabs" id="tab-list">{tabs}</div>
<div class="panels" id="panel-list">{panels}</div>
<script>
const tabs = document.querySelectorAll('.tab');
const panels = document.querySelectorAll('.panel');
tabs.forEach(tab => {{
  tab.addEventListener('click', () => {{
    tabs.forEach(t => t.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('panel-' + tab.dataset.tab).classList.add('active');
  }});
}});
// filter
document.querySelectorAll('.filter-btn').forEach(btn => {{
  btn.addEventListener('click', function() {{
    const filter = this.dataset.filter;
    const panel = this.closest('.panel');
    panel.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    this.classList.add('active');
    if (filter === 'all') {{
      panel.querySelectorAll('.date-section').forEach(s => s.style.display = '');
    }} else {{
      panel.querySelectorAll('.date-section').forEach(s => s.style.display = s.dataset.date === filter ? '' : 'none');
    }}
  }});
}});
document.getElementById('update-time').textContent = '更新: ' + new Date().toLocaleString('zh-CN');
</script>
</body>
</html>"""


def build_full_html(sheets_data, dates):
    tab_labels = [
        ('行业板块', '行业板块'),
        ('概念板块', '概念板块'),
        ('色卡图例', '色卡图例'),
        ('每日Top3强势个股', 'Top3'),
        ('非Top3板块强势个股', '非Top3'),
        ('MACD强势个股5日>10%', 'MACD5日'),
        ('MACD强势个股10日>20%', 'MACD10日'),
    ]

    tabs_html = ''
    panels_html = ''

    for i, (tab_id, tab_label) in enumerate(tab_labels):
        tabs_html += f'<div class="tab active" data-tab="{tab_id}" id="tab-btn-{tab_id}">{tab_label}</div>'

        active_class = 'active' if i == 0 else ''
        panels_html += f'<div class="panel {active_class}" id="panel-{tab_id}">'
        panels_html += sheets_data[i]
        panels_html += '</div>'

    # Fix first tab active
    tabs_html = tabs_html.replace('class="tab active"', 'class="tab"', 1)
    first_tab_idx = tabs_html.find('data-tab="' + tab_labels[0][0] + '"')
    if first_tab_idx >= 0:
        tabs_html = tabs_html[:first_tab_idx] + 'class="tab active" ' + tabs_html[first_tab_idx:]

    html = HTML_TEMPLATE.format(tabs=tabs_html, panels=panels_html)
    return html


def main():
    print('[DB_HTML] Loading data from DuckDB...')

    dates = get_recent_trade_dates(N_DAYS)
    print(f'  最近 {N_DAYS} 交易日: {[str(d) for d in dates]}')

    print('  Loading board_history...')
    dates_str = [str(d) for d in dates]
    ind_top10 = get_board_top10('行业', N_DAYS)
    con_top10 = get_board_top10('概念', N_DAYS)

    print('  Loading top3_stocks...')
    top3_data = get_top3_stocks(N_DAYS)

    print('  Loading non_top3_stocks...')
    non_top3_data = get_non_top3_stocks(N_DAYS)

    print('  Loading macd_signals...')
    macd_5d = get_macd_stocks('5d_10pct', N_DAYS)
    macd_10d = get_macd_stocks('10d_20pct', N_DAYS)

    print('  Building HTML...')
    sheets_data = [
        build_sheet1_html('行业板块', ind_top10, dates_str),
        build_sheet1_html('概念板块', con_top10, dates_str),
        build_legend_html(None, N_DAYS),
        build_top3_html(top3_data, dates_str),
        build_non_top3_html(non_top3_data, dates_str),
        build_macd_html(macd_5d, dates_str, 'MACD强势个股', '5日涨幅%'),
        build_macd_html(macd_10d, dates_str, 'MACD强势个股_10日', '10日涨幅%'),
    ]

    html = build_full_html(sheets_data, dates)

    with open(OUT_HTML, 'w', encoding='utf-8') as f:
        f.write(html)

    size = OUT_HTML.stat().st_size
    print(f'[OK] Generated: {OUT_HTML} ({size / 1024:.1f} KB)')


if __name__ == '__main__':
    main()
