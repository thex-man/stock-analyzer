# -*- coding: utf-8 -*-
"""
DuckDB 查询封装模块

提供常用查询函数，供其他脚本调用。
所有函数默认连接 data/stock.duckdb。

用法：
  from scripts.db_query import db
  db.list_top_stocks_by_score('2026-08-26', '5d_10pct', limit=10)
  db.get_stock_concepts('000001')
  db.get_board_top10('行业', '2026-08-26')
"""
import sys
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import date, datetime

import duckdb
import pandas as pd

DB_PATH = Path(__file__).parent.parent / 'data' / 'stock.duckdb'


class StockDB:
    """DuckDB 查询封装"""

    def __init__(self, db_path: Path = DB_PATH, read_only: bool = True):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(
                f'Database not found: {self.db_path}\n'
                f'Run first: python scripts/db_init.py && python scripts/db_migrate.py'
            )
        # 默认 read_only=True（避免 Windows 文件占用问题，CLI 查询不需修改）
        self.conn = duckdb.connect(str(self.db_path), read_only=read_only)

    # ====== stock_meta ======

    def get_stock_concepts(self, code: str) -> Dict:
        """获取单只股票的概念 + 主题要点"""
        row = self.conn.execute(
            "SELECT code, name, concepts, theme_points, fetch_time, total_concepts "
            "FROM stock_meta WHERE code = ?", [code]
        ).fetchone()
        if not row:
            return {}
        return {
            'code': row[0],
            'name': row[1],
            'concepts': json.loads(row[2]) if row[2] else [],
            'theme_points': json.loads(row[3]) if row[3] else [],
            'fetch_time': row[4],
            'total_concepts': row[5],
        }

    def find_stocks_by_concept(self, concept_name: str) -> pd.DataFrame:
        """按概念名搜索股票（LIKE 匹配概念 JSON 内的 name 字段）"""
        return self.conn.execute("""
            SELECT code, name, total_concepts
            FROM stock_meta
            WHERE concepts::VARCHAR LIKE ?
        """, [f'%{concept_name}%']).df()

    def search_stocks(self, keyword: str, limit: int = 20) -> pd.DataFrame:
        """按代码或名称搜索股票"""
        kw = f'%{keyword}%'
        return self.conn.execute("""
            SELECT code, name, total_concepts
            FROM stock_meta
            WHERE code LIKE ? OR name LIKE ?
            LIMIT ?
        """, [kw, kw, limit]).df()

    def all_stocks(self) -> pd.DataFrame:
        """获取所有股票元数据"""
        return self.conn.execute("SELECT * FROM stock_meta").df()

    # ====== kline ======

    def get_kline(self, code: str, start_date: str = None,
                  end_date: str = None) -> pd.DataFrame:
        """获取单只股票 K 线（默认全部）"""
        if start_date and end_date:
            return self.conn.execute("""
                SELECT * FROM kline
                WHERE code = ? AND date BETWEEN ? AND ?
                ORDER BY date
            """, [code, start_date, end_date]).df()
        elif start_date:
            return self.conn.execute("""
                SELECT * FROM kline
                WHERE code = ? AND date >= ?
                ORDER BY date
            """, [code, start_date]).df()
        else:
            return self.conn.execute(
                "SELECT * FROM kline WHERE code = ? ORDER BY date", [code]
            ).df()

    def get_latest_price(self, code: str) -> Optional[Dict]:
        """获取单只股票最新价格"""
        row = self.conn.execute("""
            SELECT date, open, high, low, close, volume
            FROM kline WHERE code = ? ORDER BY date DESC LIMIT 1
        """, [code]).fetchone()
        if not row:
            return None
        return {
            'date': row[0], 'open': row[1], 'high': row[2],
            'low': row[3], 'close': row[4], 'volume': row[5],
        }

    # ====== board_history ======

    def get_board_top10(self, board_type: str, date_str: str,
                        limit: int = 10) -> pd.DataFrame:
        """获取某日某类型板块 Top N（按涨跌幅降序）"""
        return self.conn.execute("""
            SELECT board_name, board_type, date, close, pct
            FROM board_history
            WHERE board_type = ? AND date = ?
            ORDER BY pct DESC
            LIMIT ?
        """, [board_type, date_str, limit]).df()

    def get_board_repeat(self, board_type: str = None,
                         min_appearances: int = 2,
                         limit: int = 20) -> pd.DataFrame:
        """获取最近 N 天重复上榜的板块（轮动强度）"""
        where = "WHERE board_type = ?" if board_type else ""
        params = [board_type] if board_type else []
        return self.conn.execute(f"""
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

    def get_top_stocks_by_board_pct(self, date_str: str,
                                    board_type: str = '行业',
                                    top_n_boards: int = 3) -> pd.DataFrame:
        """找某日 Top N 板块 → 这些板块内的强势股（>6%）"""
        # 先找 Top N 板块
        top_boards = self.get_board_top10(board_type, date_str, top_n_boards)
        if top_boards.empty:
            return pd.DataFrame()

        board_names = top_boards['board_name'].tolist()
        # 在 stock_meta.concepts 里搜这些板块名
        # 由于 concepts 是 JSON，这里用 LIKE 简化处理
        results = []
        for board in board_names:
            stocks = self.conn.execute("""
                SELECT code, name FROM stock_meta
                WHERE concepts::VARCHAR LIKE ?
            """, [f'%{board}%']).df()
            results.append(stocks.assign(board=board))

        if not results:
            return pd.DataFrame()
        df = pd.concat(results, ignore_index=True).drop_duplicates(subset=['code'])
        return df

    # ====== macd_signals ======

    def list_top_stocks_by_score(self, date_str: str,
                                 signal_type: str = '5d_10pct',
                                 limit: int = 10) -> pd.DataFrame:
        """某日某类信号的 Top N（按缠论分数降序）"""
        return self.conn.execute("""
            SELECT code, name, score, gain_pct, position, trend, fx, bcie
            FROM macd_signals
            WHERE date = ? AND signal_type = ?
            ORDER BY score DESC
            LIMIT ?
        """, [date_str, signal_type, limit]).df()

    def get_macd_stocks(self, signal_type: str = None,
                        date_str: str = None) -> pd.DataFrame:
        """MACD 信号列表（带筛选）"""
        sql = "SELECT * FROM macd_signals WHERE 1=1"
        params = []
        if signal_type:
            sql += " AND signal_type = ?"
            params.append(signal_type)
        if date_str:
            sql += " AND date = ?"
            params.append(date_str)
        sql += " ORDER BY score DESC"
        return self.conn.execute(sql, params).df()

    # ====== 综合查询 ======

    def get_stock_full(self, code: str) -> Dict:
        """获取单只股票的完整信息（元数据 + 最新价 + MACD 信号）"""
        meta = self.get_stock_concepts(code)
        if not meta:
            return {}

        latest = self.get_latest_price(code)
        signals = self.conn.execute("""
            SELECT date, signal_type, score, gain_pct, position, trend, fx, bcie
            FROM macd_signals WHERE code = ?
            ORDER BY date DESC, score DESC
        """, [code]).df()

        return {
            'meta': meta,
            'latest_price': latest,
            'signals': signals,
        }

    def daily_summary(self, date_str: str) -> Dict:
        """某日市场摘要"""
        top_industries = self.get_board_top10('行业', date_str)
        top_concepts = self.get_board_top10('概念', date_str)
        macd_5d = self.list_top_stocks_by_score(date_str, '5d_10pct', 10)
        macd_10d = self.list_top_stocks_by_score(date_str, '10d_20pct', 10)

        return {
            'date': date_str,
            'top_industries': top_industries,
            'top_concepts': top_concepts,
            'macd_5d_top10': macd_5d,
            'macd_10d_top10': macd_10d,
        }

    # ====== 工具方法 ======

    def table_stats(self) -> Dict[str, int]:
        """所有表的行数统计"""
        stats = {}
        for t in ['stock_meta', 'kline', 'board_history', 'macd_signals']:
            stats[t] = self.conn.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]
        return stats

    def close(self):
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        # Windows 上 DuckDB 需要主动 close，不能依赖 GC
        self.close()


# 每次调用都创建新连接（CLI 场景下避免复用已关闭的连接）
_db_instance = None


def db() -> StockDB:
    # 每次创建新连接（单次查询用完即关）
    return StockDB()


# ====== CLI ======
def main():
    import argparse
    parser = argparse.ArgumentParser(description='Stock DB Query CLI')
    parser.add_argument('cmd', help='Command: stats/concepts/kline/board/macd/full/summary')
    parser.add_argument('args', nargs='*', help='Command arguments')
    args = parser.parse_args()

    # 不使用 with（CLI 场景下需要手动关闭避免 Windows 文件占用）
    d = db()
    try:
        if args.cmd == 'stats':
            print('Table stats:')
            for t, n in d.table_stats().items():
                print(f'  {t}: {n}')

        elif args.cmd == 'concepts':
            code = args.args[0] if args.args else '000001'
            data = d.get_stock_concepts(code)
            print(f'\n{data["code"]} {data["name"]} ({data["total_concepts"]} concepts)')
            for c in data['concepts'][:5]:
                print(f'  - {c["name"]} (cid={c.get("cid")})')

        elif args.cmd == 'kline':
            code = args.args[0] if args.args else '300001'
            df = d.get_kline(code)
            print(f'\nKLine for {code}: {len(df)} rows')
            print(df.head(5).to_string())

        elif args.cmd == 'board':
            board_type = args.args[0] if args.args else '行业'
            date_str = args.args[1] if len(args.args) > 1 else '2026-08-26'
            df = d.get_board_top10(board_type, date_str)
            print(f'\nTop 10 {board_type} on {date_str}:')
            print(df.to_string())

        elif args.cmd == 'macd':
            signal = args.args[0] if args.args else '5d_10pct'
            date_str = args.args[1] if len(args.args) > 1 else '2026-08-26'
            df = d.list_top_stocks_by_score(date_str, signal, 10)
            print(f'\nTop 10 {signal} on {date_str}:')
            print(df.to_string())

        elif args.cmd == 'full':
            code = args.args[0] if args.args else '300109'
            data = d.get_stock_full(code)
            print(f'\n{data["meta"]["code"]} {data["meta"]["name"]}')
            print(f'Latest: {data["latest_price"]}')
            print(f'Signals:\n{data["signals"].to_string()}')

        elif args.cmd == 'summary':
            date_str = args.args[0] if args.args else '2026-08-26'
            s = d.daily_summary(date_str)
            print(f'\n=== {date_str} Market Summary ===')
            print(f'\nTop Industries:\n{s["top_industries"].to_string()}')
            print(f'\nTop Concepts:\n{s["top_concepts"].to_string()}')

        else:
            print(f'Unknown command: {args.cmd}')
            print('Available: stats/concepts/kline/board/macd/full/summary')
    finally:
        d.close()


if __name__ == '__main__':
    main()
