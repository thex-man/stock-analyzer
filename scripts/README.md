# DuckDB 数据库使用指南

> 替换 concept_data/ + kline_cache/ + board_history_ths/ + Excel Sheet6/7
> 创建于 2026-08-26

## 快速开始

```bash
# 1. 初始化数据库（首次）
python scripts/db_init.py
python scripts/db_migrate.py
python scripts/db_verify.py

# 2. 日常增量更新（每日复盘后调用）
python scripts/db_update.py                    # 全量更新
python scripts/db_update.py --module board     # 只更新板块
python scripts/db_update.py --module macd      # 只更新 MACD

# 3. 查询（CLI + JSON）
python scripts/stock_db.py stats --json
python scripts/stock_db.py board_top10 --type 行业 --date 2026-08-26
python scripts/stock_db.py top_stocks --date 2026-08-26 --signal 5d_10pct
python scripts/stock_db.py summary --date 2026-08-26
python scripts/stock_db.py concepts 000001

# 4. 生成 Excel（替代 board_top10_excel.py）
python scripts/db_top10_excel.py --compare

# 5. 生成 HTML（简化版）
python scripts/db_html.py
```

## 数据库信息

- **路径**：`data/stock.duckdb`（约 240 MB）
- **引擎**：DuckDB 1.5.5（嵌入式，零运维）
- **数据量**：约 10 万行（4 张表）

## 脚本清单（9 个）

| 脚本 | 用途 | 替换 |
|------|------|------|
| `db_init.py` | 初始化库 + 表结构 | - |
| `db_migrate.py` | 首次全量迁移 | - |
| `db_update.py` | 增量更新（UPSERT 幂等）| `merge_board_daily.py` 部分 |
| `db_verify.py` | 抽样对比验证 | `verify_board_data.py` |
| `db_query.py` | 详细查询 CLI + Python API | - |
| **`stock_db.py`** | **跨会话共享封装（推荐）**| **统一入口** |
| `db_top10_excel.py` | DB 版 Sheet1/2/3 生成器 | `board_top10_excel.py` |
| `db_html.py` | DB 版简化 HTML 看板 | `excel_to_html.py`（部分）|
| `README.md` | 本文档 | - |

## 跨会话访问

```python
# 方式 A：Python 直接导入（推荐）
from scripts.stock_db import q

result = q.concepts('000001')
result = q.summary('2026-08-26')
result = q.top_stocks('2026-08-26', '5d_10pct', 10)
result = q.latest_price('300109')
```

```bash
# 方式 B：CLI 跨进程（任意会话/AI）
python scripts/stock_db.py concepts 000001 --json
python scripts/stock_db.py summary --date 2026-08-26
```

## 表结构

### stock_meta（5688 行）

股票元数据 + 概念（原 `concept_data/*.json`）

| 列 | 类型 | 说明 |
|---|---|---|
| `code` | VARCHAR (PK) | 6 位股票代码 |
| `name` | VARCHAR | 股票名称 |
| `concepts` | JSON | 概念数组 |
| `theme_points` | JSON | 主题要点 |
| `fetch_time` | TIMESTAMP | 抓取时间 |
| `total_concepts` | INTEGER | 概念数 |

### kline（83836 行）

K 线（原 `kline_cache/*.csv`）

| 列 | 类型 | 说明 |
|---|---|---|
| `code` | VARCHAR (PK) | 6 位股票代码 |
| `date` | DATE (PK) | 交易日 |
| `open` / `high` / `low` / `close` | DOUBLE | OHLC |
| `volume` | BIGINT | 成交量 |

### board_history（8913 行）

板块历史（原 `data/board_history_ths/history_*.json`）

| 列 | 类型 | 说明 |
|---|---|---|
| `board_name` | VARCHAR (PK) | 板块名 |
| `board_type` | VARCHAR (PK) | 行业 / 概念 |
| `date` | DATE (PK) | 交易日 |
| `close` | DOUBLE | 收盘点位 |
| `pct` | DOUBLE | 涨跌幅 (%) |

### macd_signals（65 行/日）

MACD/缠论信号（原 Excel Sheet6/7）

| 列 | 类型 | 说明 |
|---|---|---|
| `code` | VARCHAR (PK) | 6 位股票代码 |
| `date` | DATE (PK) | 交易日 |
| `signal_type` | VARCHAR (PK) | 5d_10pct / 10d_20pct |
| `macd` / `gain_pct` / `score` | DOUBLE | 指标值 |
| `position` / `trend` / `fx` / `bcie` | VARCHAR | 缠论维度 |
| `raw_data` | JSON | 完整原始数据 |
| `fetch_time` | TIMESTAMP | 抓取时间 |

## 集成进展

| 原脚本 | DB 替代 | 状态 |
|---|---|---|
| `board_top10_excel.py` | `db_top10_excel.py` | ✅ 验证一致 |
| `verify_board_data.py` | `db_verify.py` | ✅ 30/30 |
| `merge_board_daily.py` | `db_update.py` | ✅ UPSERT |
| `excel_to_html.py` | `db_html.py`（简化版）| ✅ 6 tab |
| 跨会话共享 | `stock_db.py` | ✅ Python+CLI |
| `sheet5_wencai_v2.py` | - | ⏳ 暂未改（wencai 需登录） |
| `sheet6_wencai.py` | - | ⏳ 暂未改 |

## 文件清理（2026-08-27）

已删除 ~790 MB 源文件（迁移到 `data/_archive/` 备份）：

| 目录 | 大小 | 备份位置 |
|---|---|---|
| `concept_data/` | 785 MB | `data/_archive/concept_data_*` |
| `kline_cache/` | 3.6 MB | `data/_archive/kline_cache_*` |
| `data/board_history_ths/` | 3.9 MB | `data/_archive/board_history_ths_*` |

**回滚方法**（如需恢复）：
```bash
Move-Item data\_archive\concept_data_20260827_xxxxxx concept_data
Move-Item data\_archive\kline_cache_20260827_xxxxxx kline_cache
Move-Item data\_archive\board_history_ths_20260827_xxxxxx data\board_history_ths
```

## 注意事项

- DuckDB 在 Windows 上**只读连接**更稳定（默认 read_only=True）
- 数据库文件不要放在 OneDrive 同步目录（可能锁文件）
- 备份：`Copy-Item data\stock.duckdb data\stock.duckdb.bak.$(Get-Date -Format yyyyMMdd)`
- 写入操作（init/migrate/update）需要 read_only=False
- 概念板块数据未导入（THS 接口默认跳过概念，需 `--include-concept`）
- MACD 仅含 2026-08-26 当日数据（历史数据在 v4 Excel sheet）
