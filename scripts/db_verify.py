# -*- coding: utf-8 -*-
"""
DB 数据准确性验证脚本

抽样对比 DuckDB 数据与原始 JSON/CSV，确认迁移正确性。
"""
import sys, json, random
from pathlib import Path
import pandas as pd
import duckdb

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / 'data' / 'stock.duckdb'


def verify_stock_meta(n_samples=10):
    """验证 stock_meta vs JSON"""
    print(f'\n=== stock_meta ({n_samples} samples) ===')
    files = sorted((ROOT / 'concept_data').glob('*.json'))
    samples = random.sample(files, min(n_samples, len(files)))

    c = duckdb.connect(str(DB_PATH), read_only=True)
    errors = 0
    for f in samples:
        with open(f, 'r', encoding='utf-8') as fp:
            json_data = json.load(fp)
        code = json_data['stock_code']
        db_row = c.execute(
            'SELECT name, total_concepts FROM stock_meta WHERE code = ?', [code]
        ).fetchone()
        if not db_row:
            print(f'  [FAIL] {code}: not in DB')
            errors += 1
            continue
        if db_row[0] != json_data.get('stock_name'):
            print(f'  [FAIL] {code}: name {db_row[0]} != {json_data.get("stock_name")}')
            errors += 1
            continue
        if db_row[1] != json_data.get('total_concepts', 0):
            print(f'  [FAIL] {code}: total_concepts {db_row[1]} != {json_data.get("total_concepts")}')
            errors += 1
            continue
        print(f'  [OK] {code} {db_row[0]} ({db_row[1]} concepts)')
    c.close()
    print(f'\nResult: {n_samples - errors}/{n_samples} passed')
    return errors == 0


def verify_kline(n_samples=10):
    """验证 kline vs CSV"""
    print(f'\n=== kline ({n_samples} samples) ===')
    files = sorted((ROOT / 'kline_cache').glob('*.csv'))
    samples = random.sample(files, min(n_samples, len(files)))

    c = duckdb.connect(str(DB_PATH), read_only=True)
    errors = 0
    for f in samples:
        code = f.stem.replace('_qfq', '')
        csv_df = pd.read_csv(f)
        db_df = c.execute(
            'SELECT date, open, high, low, close, volume FROM kline WHERE code = ? ORDER BY date', [code]
        ).df()
        if len(csv_df) != len(db_df):
            print(f'  [FAIL] {code}: CSV {len(csv_df)} rows != DB {len(db_df)} rows')
            errors += 1
            continue
        # Compare last 3 rows
        for i in range(-3, 0):
            csv_row = csv_df.iloc[i]
            db_row = db_df.iloc[i]
            if abs(float(csv_row['close']) - float(db_row['close'])) > 0.01:
                print(f'  [FAIL] {code} row {i}: close CSV {csv_row["close"]} != DB {db_row["close"]}')
                errors += 1
                break
        else:
            print(f'  [OK] {code}: {len(csv_df)} rows match')
    c.close()
    print(f'\nResult: {n_samples - errors}/{n_samples} passed')
    return errors == 0


def verify_board_history():
    """验证 board_history vs JSON"""
    print(f'\n=== board_history (sample) ===')
    files = sorted((ROOT / 'data' / 'board_history_ths').glob('history_*.json'))
    latest = files[-1]
    with open(latest, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    c = duckdb.connect(str(DB_PATH), read_only=True)
    errors = 0
    samples = random.sample(list(json_data.keys()), min(10, len(json_data)))
    for board in samples:
        info = json_data[board]
        btype = info['type']
        for d in info['data'][-3:]:  # last 3 days
            # DB 里 date 是 DATE 类型，需要 'YYYY-MM-DD' 格式
            date_str = f"{d['d'][:4]}-{d['d'][4:6]}-{d['d'][6:]}"
            db_row = c.execute("""
                SELECT close, pct FROM board_history
                WHERE board_name = ? AND board_type = ? AND date = ?
            """, [board, btype, date_str]).fetchone()
            if not db_row:
                print(f'  [FAIL] {board} {d["d"]}: not in DB')
                errors += 1
                continue
            if abs(float(db_row[0]) - float(d['c'])) > 0.01:
                print(f'  [FAIL] {board} {d["d"]}: close JSON {d["c"]} != DB {db_row[0]}')
                errors += 1
        else:
            print(f'  [OK] {board} ({btype})')
    c.close()
    print(f'\nResult: {len(samples) - errors}/{len(samples)} boards passed')
    return errors == 0


def main():
    random.seed(42)
    results = {
        'stock_meta': verify_stock_meta(10),
        'kline': verify_kline(10),
        'board_history': verify_board_history(),
    }
    print('\n=== Summary ===')
    for name, ok in results.items():
        print(f'  {name}: {"PASS" if ok else "FAIL"}')
    all_ok = all(results.values())
    print(f'\nOverall: {"ALL PASS" if all_ok else "HAS FAILURES"}')
    return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
