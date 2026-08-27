# -*- coding: utf-8 -*-
"""
修复 non_top3_stocks.board_name 匹配
=====================================
方案 A: 规范化匹配（历史数据）
  - 概念名规范化：去括号/空格/后缀差异
  - 模糊匹配：子串包含
方案 B: 问财当日数据已在 sheet5 写 Excel 时带所属板块（db_sync_today 读取）
  - 本脚本重跑 db_sync_today 逻辑即可

用法: python scripts/db_fix_board_name.py
"""
import re
import duckdb
import pandas as pd
from pathlib import Path

DB = Path('data/stock.duckdb')


def normalize(name):
    """规范化概念名：去括号、空格、常见后缀"""
    if not name:
        return ''
    s = str(name)
    s = re.sub(r'[（(].*?[)）]', '', s)      # 去括号内容
    s = re.sub(r'概念|板块|指数', '', s)      # 去通用后缀
    s = re.sub(r'\s+', '', s)                # 去空格
    return s


def main():
    conn = duckdb.connect(str(DB))

    # 待修复行
    rows = conn.execute("""
        SELECT DISTINCT date, stock_code, stock_name FROM non_top3_stocks
        WHERE board_name IS NULL OR board_name = ''
    """).fetchall()
    print(f'待修复: {len(rows)} 行')

    # 概念数据缓存
    import json
    meta = conn.execute("SELECT code, concepts FROM stock_meta WHERE concepts IS NOT NULL").fetchall()
    concepts_map = {}
    for code, cj in meta:
        try:
            concepts_map[code] = [c['name'] for c in json.loads(cj)]
        except Exception:
            concepts_map[code] = []

    # 按日期取概念板块涨幅（规范化索引）
    def get_concept_pcts_norm(date_str):
        raw = conn.execute(
            "SELECT board_name, pct FROM board_history WHERE board_type='概念' AND date::VARCHAR=?",
            [date_str]).fetchall()
        # 规范化名 -> (原名, pct)
        return {normalize(n): (n, p) for n, p in raw}

    updated = 0
    for date, code, name in rows:
        date_str = str(date)[:10]
        norm_index = get_concept_pcts_norm(date_str)
        cands = concepts_map.get(code, [])
        best, best_pct = '', -999
        for c in cands:
            nc = normalize(c)
            if not nc:
                continue
            # 精确规范化匹配
            if nc in norm_index:
                orig, p = norm_index[nc]
                if p > best_pct:
                    best, best_pct = orig, p
            else:
                # 子串模糊匹配
                for nk, (orig, p) in norm_index.items():
                    if (nc and nc in nk) or (nk and nk in nc):
                        if p > best_pct:
                            best, best_pct = orig, p
                        break  # 每个概念只匹配一个
        if best:
            conn.execute(
                "UPDATE non_top3_stocks SET board_name=?, board_pct=? WHERE date=? AND stock_code=?",
                [best, best_pct, date, code])
            updated += 1

    conn.commit()
    remain = conn.execute("""
        SELECT COUNT(*) FROM non_top3_stocks WHERE board_name IS NULL OR board_name=''
    """).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM non_top3_stocks").fetchone()[0]
    print(f'[OK] 修复 {updated}/{len(rows)} 行；仍为空: {remain}/{total}')
    conn.close()


if __name__ == '__main__':
    main()
