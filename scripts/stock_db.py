# -*- coding: utf-8 -*-
"""
跨会话共享封装：stock_db

提供统一的 DB 访问入口，让任何脚本、AI 会话都能查询 stock.duckdb。

用法：

  # ===== 方式 A：Python 直接导入（同进程）=====
  from scripts.stock_db import q

  result = q.top_stocks('2026-08-26', '5d_10pct', limit=10)
  result = q.board_top10('行业', '2026-08-26')
  result = q.concepts('000001')

  # ===== 方式 B：CLI（跨进程）=====
  python scripts/stock_db.py top_stocks --date 2026-08-26 --signal 5d_10pct
  python scripts/stock_db.py board_top10 --type 行业 --date 2026-08-26
  python scripts/stock_db.py concepts 000001

设计原则：
  - 极简 API（短方法名）
  - 返回 dict / list（JSON 友好）
  - 自动关闭连接（每次调用创建新连接，避免锁文件）
  - 支持 DuckDB 只读模式（多进程安全）
"""
import sys
import json
import argparse
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

ROOT = Path(__file__).parent.parent
DB_PATH = ROOT / 'data' / 'stock.duckdb'


def _conn():
    """创建只读连接（每次新建，避免文件锁）"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f'DB not found: {DB_PATH}')
    return duckdb.connect(str(DB_PATH), read_only=True)


def _df_to_records(df: pd.DataFrame) -> list:
    """DataFrame -> list of dict（含日期序列化）"""
    records = df.to_dict(orient='records')
    for r in records:
        for k, v in list(r.items()):
            if hasattr(v, 'isoformat'):  # date/datetime
                r[k] = v.isoformat()
    return records


class StockDBQuery:
    """统一查询接口"""

    # ===== 元数据 =====

    def concepts(self, code: str) -> dict:
        """获取单只股票的概念 + 主题要点"""
        with _conn() as c:
            row = c.execute("""
                SELECT code, name, concepts, theme_points, fetch_time, total_concepts
                FROM stock_meta WHERE code = ?
            """, [code]).fetchone()
        if not row:
            return {'error': f'code {code} not found'}
        import json as _json
        return {
            'code': row[0],
            'name': row[1],
            'concepts': _json.loads(row[2]) if row[2] else [],
            'theme_points': _json.loads(row[3]) if row[3] else [],
            'fetch_time': row[4].isoformat() if row[4] else None,
            'total_concepts': row[5],
        }

    def search(self, keyword: str, limit: int = 20) -> list:
        """按代码或名称搜索"""
        kw = f'%{keyword}%'
        with _conn() as c:
            df = c.execute("""
                SELECT code, name, total_concepts FROM stock_meta
                WHERE code LIKE ? OR name LIKE ?
                LIMIT ?
            """, [kw, kw, limit]).df()
        return _df_to_records(df)

    def find_by_concept(self, concept_name: str, limit: int = 100) -> list:
        """按概念名搜索股票"""
        with _conn() as c:
            df = c.execute("""
                SELECT code, name, total_concepts FROM stock_meta
                WHERE concepts::VARCHAR LIKE ?
                LIMIT ?
            """, [f'%{concept_name}%', limit]).df()
        return _df_to_records(df)

    # ===== K 线 =====

    def kline(self, code: str, start: Optional[str] = None,
              end: Optional[str] = None, limit: int = 100) -> list:
        """获取 K 线"""
        with _conn() as c:
            if start and end:
                df = c.execute("""
                    SELECT * FROM kline WHERE code = ?
                    AND date BETWEEN ? AND ?
                    ORDER BY date LIMIT ?
                """, [code, start, end, limit]).df()
            else:
                df = c.execute("""
                    SELECT * FROM kline WHERE code = ?
                    ORDER BY date DESC LIMIT ?
                """, [code, limit]).df()
        return _df_to_records(df)

    def latest_price(self, code: str) -> dict:
        """最新价"""
        with _conn() as c:
            row = c.execute("""
                SELECT date, open, high, low, close, volume
                FROM kline WHERE code = ? ORDER BY date DESC LIMIT 1
            """, [code]).fetchone()
        if not row:
            return {'error': f'no kline for {code}'}
        return {
            'code': code,
            'date': row[0].isoformat() if hasattr(row[0], 'isoformat') else row[0],
            'open': float(row[1]) if row[1] else None,
            'high': float(row[2]) if row[2] else None,
            'low': float(row[3]) if row[3] else None,
            'close': float(row[4]) if row[4] else None,
            'volume': int(row[5]) if row[5] else None,
        }

    # ===== 板块 =====

    def board_top10(self, board_type: str, date: str, limit: int = 10) -> list:
        """某日某类型板块 Top N"""
        with _conn() as c:
            df = c.execute("""
                SELECT board_name, board_type, date, close, pct
                FROM board_history
                WHERE board_type = ? AND date = ?
                ORDER BY pct DESC LIMIT ?
            """, [board_type, date, limit]).df()
        return _df_to_records(df)

    def board_repeat(self, board_type: Optional[str] = None,
                     min_appearances: int = 2, limit: int = 20) -> list:
        """重复上榜板块"""
        where = "WHERE board_type = ?" if board_type else ""
        params = [board_type] if board_type else []
        with _conn() as c:
            df = c.execute(f"""
                SELECT board_name, board_type,
                       COUNT(*) as appearances,
                       AVG(pct) as avg_pct,
                       MAX(pct) as max_pct
                FROM board_history
                {where}
                GROUP BY board_name, board_type
                HAVING COUNT(*) >= ?
                ORDER BY appearances DESC, avg_pct DESC
                LIMIT ?
            """, params + [min_appearances, limit]).df()
        return _df_to_records(df)

    # ===== MACD =====

    def top_stocks(self, date: str, signal: str = '5d_10pct', limit: int = 10) -> list:
        """MACD 强势股 Top N"""
        with _conn() as c:
            df = c.execute("""
                SELECT code, name, score, gain_pct, position, trend, fx, bcie
                FROM macd_signals
                WHERE date = ? AND signal_type = ?
                ORDER BY score DESC LIMIT ?
            """, [date, signal, limit]).df()
        return _df_to_records(df)

    # ===== 综合 =====

    def summary(self, date: str) -> dict:
        """每日摘要"""
        return {
            'date': date,
            'top_industries': self.board_top10('行业', date),
            'top_concepts': self.board_top10('概念', date),
            'macd_5d_top10': self.top_stocks(date, '5d_10pct', 10),
            'macd_10d_top10': self.top_stocks(date, '10d_20pct', 10),
        }

    def stock_full(self, code: str) -> dict:
        """单只股票完整信息"""
        meta = self.concepts(code)
        if 'error' in meta:
            return meta
        return {
            'meta': meta,
            'latest_price': self.latest_price(code),
            'macd_signals': [
                r for r in (
                    self.top_stocks(d, '5d_10pct', 100) +
                    self.top_stocks(d, '10d_20pct', 100)
                ) if r.get('code') == code
            ],
        }

    def stats(self) -> dict:
        """表统计"""
        with _conn() as c:
            result = {}
            for t in ['stock_meta', 'kline', 'board_history', 'macd_signals']:
                result[t] = c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        return result


# 全局单例
q = StockDBQuery()


# ===== CLI =====

def main():
    parser = argparse.ArgumentParser(description='Stock DB 跨会话查询')
    parser.add_argument('cmd', help='Command')
    parser.add_argument('args', nargs='*', help='Arguments')
    parser.add_argument('--date', help='Date (YYYY-MM-DD)')
    parser.add_argument('--type', help='Board type: 行业/概念')
    parser.add_argument('--signal', help='MACD signal: 5d_10pct/10d_20pct')
    parser.add_argument('--limit', type=int, default=10)
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    args = parser.parse_args()

    result = None
    if args.cmd == 'stats':
        result = q.stats()
    elif args.cmd == 'concepts':
        result = q.concepts(args.args[0])
    elif args.cmd == 'search':
        result = q.search(args.args[0], args.limit)
    elif args.cmd == 'find_by_concept':
        result = q.find_by_concept(args.args[0], args.limit)
    elif args.cmd == 'kline':
        result = q.kline(args.args[0], limit=args.limit)
    elif args.cmd == 'latest':
        result = q.latest_price(args.args[0])
    elif args.cmd == 'board_top10':
        result = q.board_top10(args.type or '行业', args.date, args.limit)
    elif args.cmd == 'board_repeat':
        result = q.board_repeat(args.type, min_appearances=2, limit=args.limit)
    elif args.cmd == 'top_stocks':
        result = q.top_stocks(args.date, args.signal or '5d_10pct', args.limit)
    elif args.cmd == 'summary':
        result = q.summary(args.date or '2026-08-26')
    elif args.cmd == 'full':
        result = q.stock_full(args.args[0])
    else:
        print(f'Unknown command: {args.cmd}', file=sys.stderr)
        print('Available: stats/concepts/search/find_by_concept/kline/latest/board_top10/board_repeat/top_stocks/summary/full', file=sys.stderr)
        sys.exit(1)

    if args.json or result is not None:
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))


if __name__ == '__main__':
    main()
