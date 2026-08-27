# -*- coding: utf-8 -*-
"""
Top3 历史回算（行业板块口径，v3.2）
====================================
逻辑: 当日行业涨幅Top3 × data/industry_members.json 成分 × kline涨幅>8%
本地计算，无 API 调用。成分映射由 fetch_industry_members.py 生成（问财）。
幂等: 每日先删旧回算行，保留 wencai 真实数据日。
用法: python scripts/db_backfill_top3.py
"""
import json
from pathlib import Path
import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
DB = ROOT / 'data' / 'stock.duckdb'
CONCEPT_DIR = ROOT / 'data' / 'concept_data'

N_DAYS = 10
ts = pd.Timestamp.now()


def load_reverse_index():
    """concept -> [codes] 反查索引"""
    idx = {}
    for f in CONCEPT_DIR.glob('*_concepts.json'):
        code = f.stem.replace('_concepts', '')
        try:
            with open(f, encoding='utf-8') as fp:
                d = json.load(fp)
            for c in d.get('concepts', []):
                name = c.get('name')
                if name:
                    idx.setdefault(name, set()).add(code)
        except Exception:
            continue
    return idx


def main():
    conn = duckdb.connect(str(DB))
    dates = [d for (d,) in conn.execute(
        f"SELECT DISTINCT date FROM board_history ORDER BY date DESC LIMIT {N_DAYS}").fetchall()]
    print(f'回算日期: {[str(d)[:10] for d in dates]}')

    print('[1/3] 加载行业成分映射...')
    import json as _json
    from pathlib import Path as _Path
    mf = _Path(r'D:\stock\tool\stock\data\industry_members.json')
    rev_idx = {}
    if mf.exists():
        rev_idx = {k: set(v) for k, v in _json.load(open(mf, encoding='utf-8')).items()}
    empty = [n for n, v in rev_idx.items() if len(v) < 3]
    print(f'  {len(rev_idx)} 个行业成分映射' + (f'（⚠️ {len(empty)} 个为空: {empty[:5]}，先跑 fetch_industry_members.py）' if empty else ''))

    # 最新 wencai 真实数据日保护
    real_dates = {str(r[0])[:10] for r in conn.execute(
        "SELECT DISTINCT date FROM top3_stocks WHERE stock_code != '-'").fetchall()}
    print(f'  wencai 真实日（保留）: {sorted(real_dates)}')

    total = 0
    for d in dates:
        d_str = str(d)[:10]
        if d_str in real_dates:
            print(f'  {d_str}: wencai 真实日，跳过')
            continue
        # 当日行业 Top3
        top3 = conn.execute("""
            SELECT board_name, pct FROM board_history
            WHERE board_type='行业' AND date::VARCHAR=?
            ORDER BY pct DESC LIMIT 3
        """, [d_str]).fetchall()
        if not top3:
            print(f'  {d_str}: 无行业数据，跳过')
            continue

        # kline 当日涨幅（LAG 必须在过滤前计算，否则 prev_close 全 NULL）
        kl = conn.execute("""
            SELECT code, date, close,
                   LAG(close) OVER (PARTITION BY code ORDER BY date) AS prev_close
            FROM kline WHERE date <= ?::DATE
        """, [d_str]).df()
        kl = kl.dropna(subset=['prev_close'])
        kl = kl[kl['date'].astype(str).str[:10] == d_str]
        kl['pct'] = (kl['close'] / kl['prev_close'] - 1) * 100
        gain8 = kl[kl['pct'] > 8]
        gain_map = {r['code']: round(r['pct'], 2) for _, r in gain8.iterrows()}
        names = dict(conn.execute("SELECT code, name FROM stock_meta").fetchall())

        rows = []
        for rank, (bname, bpct) in enumerate(top3, 1):
            members = rev_idx.get(bname, set())
            hits = [(c, gain_map[c]) for c in members if c in gain_map]
            hits.sort(key=lambda x: -x[1])
            if not hits:
                rows.append((d_str, bname, '行业', bpct, rank, '-', '—', 0, ts))
            for code, p in hits:
                rows.append((d_str, bname, '行业', bpct, rank, code, names.get(code, code), p, ts))

        df = pd.DataFrame(rows, columns=['date', 'board_name', 'board_type', 'board_pct', 'rank_', 'stock_code', 'stock_name', 'stock_pct', 'fetch_time'])
        conn.execute("DELETE FROM top3_stocks WHERE date::VARCHAR=?", [d_str])
        conn.execute("""INSERT INTO top3_stocks (date, board_name, board_type, board_pct, rank_, stock_code, stock_name, stock_pct, fetch_time)
                        SELECT date::DATE, board_name, board_type, board_pct, rank_, stock_code, stock_name, stock_pct, fetch_time FROM df""")
        real_hits = len(df[df['stock_code'] != '-'])
        total += real_hits
        print(f'  {d_str}: {top3[0][0]} 等 Top3, 个股 {real_hits} 只入榜')

    conn.commit()
    print(f'\n[OK] Top3 历史回算完成，共 {total} 只个股')
    df3 = conn.execute("SELECT date, COUNT(*) FROM top3_stocks GROUP BY date ORDER BY date DESC").df()
    print(df3.to_string())
    conn.close()


if __name__ == '__main__':
    main()
