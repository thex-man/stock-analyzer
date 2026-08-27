# DATA_DICTIONARY.md — stock.duckdb 数据字典

> 数据库：`D:\stock\tool\stock\data\stock.duckdb`（DuckDB，单写者）
> 更新：2026-08-28 02:40 | 维护：每日复盘流程自动写入 + `scripts/db_import_members.py` 映射入库
> ⚠️ DuckDB 被锁时：`Get-Process python` 找占锁进程，确认非任务后 `Stop-Process -Id <pid> -Force`

## 总览（实体关系）

```
stock_meta (5688 只股票主档)
   │ code
   ├──< kline              每股×每日K线（新浪源）
   ├──< macd_signals       每股×每日 MACD 信号（wencai+缠论打分）
   ├──< top3_stocks        当日行业Top3板块内 >8% 个股
   ├──< non_top3_stocks    全市场 >6% 且不在Top3行业的个股
   └──< board_members *    股票↔板块映射（THS行业/THS概念，待导入）
        │ board_name
        └──> board_history 板块×每日指数（行业90/概念375，THS口径）

stock_industry_sw *        股票→申万三级（待导入）
```

## 表清单

### stock_meta — 股票主档
| 列 | 类型 | 说明 |
|---|---|---|
| code | VARCHAR PK | 6位代码，如 600519 |
| name | VARCHAR | 股票简称 |
| concepts | JSON | THS概念列表 `[{name, cid, top_stocks, reason}]`（6/17旧数据，待刷新） |
| theme_points | JSON | 题材要点 |
| fetch_time | VARCHAR | 抓取时间 |

### kline — 日K线（117015 行）
| 列 | 类型 | 说明 |
|---|---|---|
| code+date | PK | 股票×交易日 |
| open/high/low/close | DOUBLE | 新浪前复权 |
| volume | BIGINT | 成交量 |

来源：`scripts/kline_full_pull.py`（新浪，4575只，限速0.15s）。**缺口补跑**：同命令幂等。

### board_history — 板块指数（8835 行）
| 列 | 类型 | 说明 |
|---|---|---|
| board_name+board_type+date | PK | 板块×类型×日 |
| board_type | VARCHAR | '行业'(90个) / '概念'(375个)，THS口径 |
| close | DOUBLE | 板块指数收盘 |
| pct | DOUBLE | 涨幅%（**相邻收盘自算**，不信 summary 快照） |

来源：`merge_board_daily.py`（每日增量）+ `backfill_ths_range.py`（区间重抓）。
质量门禁：保存前 `check_stale()` 相邻日 identical≥90% 拒写（防 THS 旧值 bug）。

### top3_stocks — 行业Top3强势股（114 行）
| 列 | 说明 |
|---|---|
| date+board_name+rank_+stock_code | 复合键 |
| board_name / board_type='行业' | 当日行业涨幅Top3板块 |
| board_pct | 板块涨幅 |
| rank_ | 板块排名 1-3 |
| stock_pct | 个股涨幅（>8% 入榜） |

口径（v3.2，2026-08-28 起）：**行业板块**。
当日=wencai 真实数据（Sheet4）；历史=`db_backfill_top3.py` 回算（行业Top3 × `data/industry_members.json` 成分 × kline>8%）。

### non_top3_stocks — 非Top3强势股（1178 行）
当日 >6% 且不在 Top3 行业的个股。当日=wencai（Sheet5）；历史=`db_backfill_history.py`（kline 回算）。board_name 列为个股所属概念（可空，待用 board_members 补全）。

### macd_signals — MACD 信号（2752 行）
signal_type: '5d_10pct'（5日>10%）/ '10d_20pct'（10日>20%）。
score/position/trend/fx/bcie 为缠论打分与结构（wencai 查询 + 本地缠论分析）。来源：Sheet6/7 → `db_sync_today.py`。

### db_meta — 元数据（key-value）
版本、最后同步时间等。

## 待导入（爬虫跑完后 `python scripts/db_import_members.py`）

### board_members — 股票↔板块映射
```
board_name + board_type + stock_code  PK
board_type: 'THS行业'（问财90行业）/ 'THS概念'（F10 concept_data）
```
来源文件：`data/industry_members.json`、`data/concept_data/*.json`

### stock_industry_sw — 申万行业
```
stock_code PK, sw_l1, sw_l2, sw_l3, sw_l3_members
```
来源：`data/industry_data/*.json`（F10 field.html 三级行业分类）

## 口径警告（勿混用）
| 口径 | 用途 | 表 |
|---|---|---|
| THS 90 行业 | Top3 筛选、行业轮动 | board_history(行业)、board_members(THS行业) |
| THS 375 概念 | 概念轮动、个股概念展示 | board_history(概念)、board_members(THS概念) |
| 申万三级 | 备用分析维度 | stock_industry_sw |

问财 `所属行业` 返回申万口径，**不能**直接和 THS 行业 join。

## 日常更新链（详见 workflow_daily_review.md v3.2）
```
merge_board_daily.py（行业） → db_import_concepts_spot.py（概念1次）
→ db_update.py --module board → wencai Sheet4/5/6/7
→ db_sync_today.py → db_backfill_top3.py → db_html.py
```
映射刷新：行业季度、概念月度（`crawler_all_concepts.py`、`fetch_industry_members.py`，均断点续跑）。
