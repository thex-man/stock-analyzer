# coding: utf-8
"""
每日复盘脚本 daily_review.py
=====================================
功能：使用 akshare（新丽财经）实时接口获取
  1. 行业板块涨幅前 N
  2. 概念板块涨幅前 N

注意：akshare.stock_sector_spot 不支持历史日期查询，只能拿当日实时榜。
要查历史日请用 daily_review_history.py（待办）。

用法：
    python daily_review.py            # 默认今日，直接运行，打印复盘结果
    python daily_review.py --save     # 同时将结果保存为 Excel（data/每日复盘_日期.xlsx）
    python daily_review.py --top 20   # 取前 N（默认 10）
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import akshare as ak

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# === 常量配置 ===
DEFAULT_TOP_N = 10
SCRIPT_DIR = Path(__file__).resolve().parent
SAVE_DIR = SCRIPT_DIR / "data"            # 改为绝对路径，避免依赖 cwd

# 板块名候选关键字（按优先级匹配）
_NAME_KEYWORDS = ("板块名称", "行业名称", "概念名称", "行业", "概念", "名称", "板块")
# 涨跌幅候选关键字
_PCT_KEYWORDS = ("涨跌幅", "涨幅", "涨跌幅(%)")

# 新浪板块接口 indicator → akshare.stock_sector_spot
SECTOR_INDICATORS = {
    "行业板块": "行业",
    "概念板块": "概念",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每日复盘：获取行业/概念板块涨幅排行")
    parser.add_argument("--save", action="store_true", help="同时保存结果到 Excel")
    parser.add_argument(
        "--top", type=int, default=DEFAULT_TOP_N, help="取前 N 名（默认 10）"
    )
    args = parser.parse_args()
    if args.top <= 0:
        parser.error(f"--top 必须为正整数: {args.top}")
    return args


def query_boards(title: str, indicator: str) -> tuple[pd.DataFrame, Optional[str]]:
    """
    调用 akshare 拿板块实时数据。
    返回 (DataFrame, error_message)：
      - 成功：error_message=None
      - 失败：DataFrame 为空，error_message 为可读错误
    """
    try:
        df = ak.stock_sector_spot(indicator=indicator)
        if df is None:
            return pd.DataFrame(), "akshare 返回 None"
        if df.empty:
            return pd.DataFrame(), "akshare 返回空 DataFrame"
        logger.info("查询 '%s' (indicator=%s) 成功，共 %d 条", title, indicator, len(df))
        return df, None
    except Exception as e:
        logger.error("查询 '%s' (indicator=%s) 出错: %s", title, indicator, e)
        return pd.DataFrame(), f"{type(e).__name__}: {e}"


def find_board_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str], list[str]]:
    """
    从 DataFrame 列里识别板块名称列 + 涨跌幅列。
    返回 (name_col, pct_col, warnings)。
    如果有多个候选列同名同字段，加入 warnings 让用户知情。
    """
    warnings: list[str] = []
    name_col = None
    pct_col = None

    name_candidates = [c for c in df.columns if any(k in str(c) for k in _NAME_KEYWORDS)]
    pct_candidates = [c for c in df.columns if any(k in str(c) for k in _PCT_KEYWORDS)]

    if name_candidates:
        name_col = name_candidates[0]
        if len(name_candidates) > 1:
            warnings.append(f"板块名称列不唯一，使用 '{name_col}'（候选: {name_candidates}）")
    if pct_candidates:
        pct_col = pct_candidates[0]
        if len(pct_candidates) > 1:
            warnings.append(f"涨跌幅列不唯一，使用 '{pct_col}'（候选: {pct_candidates}）")

    return name_col, pct_col, warnings


def coerce_pct_column(df: pd.DataFrame, pct_col: str) -> tuple[pd.Series, list[str]]:
    """
    把涨跌幅列转成 float。
    返回 (numeric_series, warnings)：
      - 原列保持不动，调用方用 numeric_series 排序
      - 转换失败的行变成 NaN，会被 sort_values 自动排到最后
    """
    warnings: list[str] = []
    series = df[pct_col]
    # 处理可能的 % 符号、千分位、字符串数字
    def _to_float(v):
        if pd.isna(v):
            return float("nan")
        s = str(v).strip().rstrip("%").replace(",", "")
        try:
            return float(s)
        except (ValueError, TypeError):
            return float("nan")

    numeric = series.apply(_to_float)
    bad = numeric.isna().sum() - series.isna().sum()
    if bad > 0:
        warnings.append(f"涨跌幅列 '{pct_col}' 有 {bad} 行无法转 float，将排到末尾")
    return numeric, warnings


def print_top(df: pd.DataFrame, title: str, top_n: int, target_date: Optional[str]) -> list[str]:
    """
    打印板块涨幅前 top_n。
    返回 warnings（用于汇总）。
    """
    all_warnings: list[str] = []
    print(f"\n【{title}涨幅前{top_n}】")
    if df.empty:
        print("  未获取到数据")
        return all_warnings

    name_col, pct_col, warnings = find_board_columns(df)
    all_warnings.extend(warnings)

    if not (name_col and pct_col):
        print("  ⚠️ 无法识别板块名称/涨跌幅列，打印原始数据：")
        print(df.head(top_n).to_string(index=False))
        return all_warnings

    # 关键修复：转 float → 排序 → 截前 N（不是先 head 再排序）
    numeric, pct_warnings = coerce_pct_column(df, pct_col)
    all_warnings.extend(pct_warnings)

    work = df.assign(_pct_num=numeric)
    work = work.sort_values(by="_pct_num", ascending=False, na_position="last").head(top_n)

    print(f"  {'排名':<4}{'板块名称':<22}{'涨跌幅':<12}")
    print("  " + "-" * 40)
    for idx, (_, row) in enumerate(work.iterrows(), 1):
        name = str(row[name_col])[:20]
        pct_display = f"{row['_pct_num']:.2f}%" if pd.notna(row["_pct_num"]) else "N/A"
        print(f"  {idx:<6}{name:<22}{pct_display:<12}")

    if target_date:
        print(f"  （数据日期: {target_date}）")
    return all_warnings


def save_to_excel(dfs: dict[str, pd.DataFrame], target_date: Optional[str]) -> tuple[Optional[Path], Optional[str]]:
    """
    保存到 Excel。同名文件已存在则跳过（不覆盖）。
    文件名规则：
      - 有 --date：每日复盘_YYYYMMDD.xlsx（一日一文件，覆盖保护）
      - 没 --date：每日复盘_YYYYMMDD_HHMMSS.xlsx（按当前时间，保证唯一）
    返回 (saved_path, error_message)。
    """
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    if target_date:
        safe_tag = target_date.replace("-", "")  # 20250813
    else:
        safe_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = SAVE_DIR / f"每日复盘_{safe_tag}.xlsx"

    if filename.exists():
        return None, f"Excel 已存在，跳过保存: {filename}"

    try:
        with pd.ExcelWriter(filename, engine="openpyxl") as writer:
            for sheet_name, df in dfs.items():
                # 存全量（不是只存 top_n）
                df.to_excel(writer, sheet_name=sheet_name[:31], index=False)
    except Exception as e:
        return None, f"保存 Excel 失败: {type(e).__name__}: {e}"

    print(f"\n数据已保存到: {filename}")
    return filename, None


def save_to_html(dfs: dict[str, pd.DataFrame], safe_tag: str) -> tuple[Optional[Path], Optional[str]]:
    """将行业+概念板块数据生成独立 HTML 看板"""
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = SAVE_DIR / f"每日复盘看板_{safe_tag}.html"

    def build_board_table(df: pd.DataFrame, title: str) -> str:
        name_col, pct_col = None, None
        for c in df.columns:
            if not name_col and any(k in str(c) for k in _NAME_KEYWORDS): name_col = c
            if not pct_col and any(k in str(c) for k in _PCT_KEYWORDS): pct_col = c
        if not (name_col and pct_col):
            return f'<p>无法解析 {title}</p>'

        def to_float(v):
            try: return float(str(v).strip().rstrip('%').replace(',', ''))
            except: return 0.0

        rows = df.sort_values(pct_col, ascending=False).iterrows()
        html = f'<div id="tab-{title}" class="panel">'
        html += '<div class="table-wrap"><table>'
        html += f'<thead><tr><th>排名</th><th>{title}</th><th>涨跌幅</th></tr></thead><tbody>'
        for rank, (_, row) in enumerate(rows, 1):
            pct = to_float(row[pct_col])
            pct_str = f'{pct:+.2f}%'
            pct_color = '#f87171' if pct > 0 else '#60a5fa'
            name = str(row[name_col])[:24]
            html += f'<tr><td style="text-align:center;font-weight:700">{rank}</td>'
            html += f'<td style="text-align:left;padding-left:12px">{name}</td>'
            html += f'<td style="text-align:right;color:{pct_color};font-weight:700;padding-right:12px">{pct_str}</td></tr>'
        html += '</tbody></table></div></div>'
        return html

    tab_hy = build_board_table(dfs.get('行业板块', pd.DataFrame()), '行业板块')
    tab_gn = build_board_table(dfs.get('概念板块', pd.DataFrame()), '概念板块')

    html = f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>每日复盘 {safe_tag[:8]}</title>
<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }}
.header {{ background: linear-gradient(135deg, #16213e, #0f3460); padding: 20px 32px; border-bottom: 1px solid #2a5298; }}
.header h1 {{ font-size: 1.5rem; color: #e2e8f0; }}
.header p {{ font-size: 0.85rem; color: #94a3b8; margin-top: 4px; }}
.tabs {{ display: flex; gap: 4px; padding: 16px 32px 0; background: #16213e; flex-wrap: wrap; }}
.tab {{ padding: 10px 20px; background: #1e2d4a; border: none; border-radius: 8px 8px 0 0; color: #94a3b8; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; }}
.tab:hover {{ background: #2a3f6f; color: #e2e8f0; }}
.tab.active {{ background: #1a1a2e; color: #60a5fa; font-weight: 600; }}
.panel {{ display: none; padding: 24px 32px; }}
.panel.active {{ display: block; }}
.table-wrap {{ overflow-x: auto; border-radius: 8px; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; min-width: 400px; }}
th {{ background: #1e2d4a; color: #93c5fd; padding: 10px 16px; text-align: center; font-weight: 600; border: 1px solid #2a3f6f; position: sticky; top: 0; }}
td {{ padding: 9px 16px; border: 1px solid #2a2a4a; }}
tr:hover td {{ background: #2a2f4a; }}
</style>
</head>
<body>
<div class="header">
  <h1>📊 每日复盘看板</h1>
  <p>{safe_tag[:4]}年{safe_tag[4:6]}月{safe_tag[6:8]}日 &nbsp;|&nbsp; 数据来源：同花顺</p>
</div>
<div class="tabs">
  <button class="tab active" onclick="showTab('行业板块', this)">行业板块</button>
  <button class="tab" onclick="showTab('概念板块', this)">概念板块</button>
</div>
{tab_hy}
{tab_gn}
<script>
function showTab(name, btn) {{
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('tab-' + name).classList.add('active');
  if (btn) btn.classList.add('active');
}}
document.addEventListener('DOMContentLoaded', () => {{
  const hash = location.hash.slice(1);
  if (hash) {{
    const btn = [...document.querySelectorAll('.tab')].find(t => t.textContent.includes(hash));
    if (btn) showTab(hash, btn);
  }}
}});
</script>
</body>
</html>'''
    try:
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return out_path, None
    except Exception as e:
        return None, f'保存 HTML 失败: {type(e).__name__}: {e}'


def main() -> int:
    args = parse_args()
    target_date = None  # akshare 不支持历史日查询
    top_n = args.top

    today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 60)
    print(f"  每日复盘 - 板块涨幅排行")
    print(f"  查询时间: {today}")
    if target_date:
        print(f"  数据日期: {target_date}")
    print(f"  取前: {top_n} 名")
    print("=" * 60)

    queries = [
        ("行业板块", SECTOR_INDICATORS["行业板块"]),
        ("概念板块", SECTOR_INDICATORS["概念板块"]),
    ]

    results: dict[str, pd.DataFrame] = {}
    error_summary: list[str] = []
    warning_summary: list[str] = []

    for title, indicator in queries:
        df, err = query_boards(title, indicator)
        results[title] = df
        if err:
            error_summary.append(f"{title}: {err}")
        warnings = print_top(df, title, top_n, target_date)
        warning_summary.extend(f"{title}: {w}" for w in warnings)
        print("-" * 60)

    # 汇总
    if warning_summary:
        print("\n【警告汇总】")
        for w in warning_summary:
            print(f"  - {w}")
    if error_summary:
        print("\n【错误汇总】")
        for e in error_summary:
            print(f"  - {e}")
        # 至少一个 query 失败 → exit code 非 0
        print(f"\n复盘完成（{len(error_summary)}/{len(queries)} 个查询失败）。")
        return 2

    if args.save:
        safe_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved, save_err = save_to_excel(results, target_date)
        if save_err:
            print(f"\n{save_err}")
        else:
            html_path, html_err = save_to_html(results, safe_tag)
            if html_err:
                print(f"\n{html_err}")
            else:
                print(f"HTML 已生成: {html_path}")

    if not error_summary:
        print("\n复盘完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())