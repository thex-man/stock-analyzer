# 每日复盘 SOP v3.2

> 最后更新：2026-08-28
> 触发词：**今日复盘** / 每日复盘 / 当日复盘
> 工作目录：`D:\stock\tool\stock`
> 架构：**DB 先行**——DuckDB 是唯一数据真相，HTML 从 DB 生成

---

## 0. 流程速览（新 session 第一眼必读）

```
Step 0 数据入库 ──→ Step 1 wencai 抓取 ──→ Step 2 同步 DB ──→ Step 3 生成 HTML
（板块缓存+概念）    （Sheet4/5/6/7）        （db_sync_today）    （db_html）
```

**最短路径（一键）**：
```powershell
cd D:\stock\tool\stock
# Step 0: 数据入库（⚠️ PowerShell 5.1 不支持 `||`，用 if ($LASTEXITCODE -ne 0) {...} 代替）
python merge_board_daily.py --include-concept       # 行业+概念板块（THS，91+375 次，用户已确认 A 方案）
# Step 1: wencai 抓取（写 v4 Excel）
python add_top3_stocks_sheet.py                # Sheet4 Top3（~10 次）
python sheet5_wencai_v2.py                     # Sheet5 非Top3（~10 次）
python sheet6_wencai.py                        # Sheet6 MACD 5日（~23 次）
python sheet6_macd_chan_10d.py                 # Sheet7 MACD 10日（~23 次）
# Step 2: 同步 DB
python scripts/db_sync_today.py                # v4 Sheet4/5/6/7 → DB（幂等）
python scripts/db_backfill_top3.py             # 行业口径回算 Top3 历史补漏（纯本地）
python scripts/kline_full_pull.py             # kline 每日增量（新浪 ~4550 次，已确认；v2 动态日期版）
# Step 3: 生成 HTML（纯本地，从 DB 读）
python scripts/db_html.py                      # → data/每日复盘看板.html（7 tab）
```

**预计耗时**：5-8 分钟（wencai 查询为主）

---

## 1. 架构说明（v3.0 核心变化）

### 数据流

```
akshare（板块）─┐
wencai（个股）─┼─→ v4 Excel（当日中转）→ db_sync_today.py → DuckDB → db_html.py → HTML
kline（K线）───┘                        （历史回算脚本）↗
```

### DuckDB 表（`data/stock.duckdb`）

| 表 | 内容 | 更新方式 |
|---|---|---|
| `stock_meta` | 5688 只股票名称/概念归属 | `db_update.py` |
| `kline` | 主板+创业板 K线（4571 只） | `kline_full_pull.py`（新浪源） |
| `board_history` | 行业/概念板块每日涨幅（20 日） | `db_update.py` + `db_import_concepts_spot.py` |
| `top3_stocks` | **行业**Top3板块 × 成分 × >8% 个股（v3.2 改行业口径） | `db_sync_today.py` + `db_backfill_top3.py` |
| `non_top3_stocks` | >6% 且不在Top3板块（全市场） | `db_sync_today.py` + `db_backfill_history.py` |
| `macd_signals` | MACD 信号（16日历史+增量） | `db_sync_today.py` |
| `board_members` | 股票↔板块映射（THS行业/THS概念） | `db_import_members.py`（季度/月度刷新） |
| `stock_industry_sw` | 股票→申万三级 | `db_import_members.py` |

完整数据字典见 `DATA_DICTIONARY.md`（口径警告：THS行业/THS概念/申万 勿混用）。

### 与 v2.x 的区别

| 项 | v2.x（旧） | v3.0（现） |
|---|---|---|
| 数据真相 | v4 Excel | **DuckDB** |
| HTML 来源 | excel_to_html.py 读 Excel | **db_html.py 读 DB** |
| HTML tab 数 | 9 | **7** |
| Top3 口径 | 行业板块 | v3.0 曾改概念，**v3.2 改回行业**（industry_members.json，可回算） |
| Sheet 数 | 19 | 8（Sheet9-18 已删） |
| MACD v2 滚动 | 有 | **已删**（sheet6_macd_roll_10d.py / inject_macd_tab.py DEPRECATED） |

---

## 2. 交易日判断规则（9:15 前必读）

| 当前时间 | 实际交易日 |
|---------|-----------|
| 工作日 00:00 - 09:14 | 昨天（上一交易日） |
| 工作日 09:15 - 23:59 | 今天 |
| 节假日 / 周末 | 上一交易日 |

**代码口径**（各脚本已内置）：
```python
if now.time() < dtime(9, 15):
    trade_date = now - timedelta(days=1)   # 凌晨复盘 = 上一交易日
```

**踩坑**：
- 问财无登录 session 时日期参数无效，只返回当日 → 只用"今日"查询
- **实测细则（2026-08-28）**：`日期+涨幅` 简单条件历史查询有效（返回列为今日值但筛选按历史执行）；`日期+MACD/区间涨幅` 指标组合日期参数被忽略、返回当日数据 → 指标类历史只能本地回算（backfill_macd_date.py）
- wencai 脚本用**系统日期**，凌晨跑时 `db_sync_today.py` 会自动转成上一交易日

---

## 3. 调用次数预算

| 步骤 | 次数 | 累计 |
|---|---|---|
| merge_board_daily.py（行业+概念） | 466 | 466 |
| add_top3_stocks_sheet.py | ~10 wencai | ~103 |
| sheet5_wencai_v2.py | ~10 wencai | ~113 |
| sheet6_wencai.py | ~23 wencai | ~136 |
| sheet6_macd_chan_10d.py | ~23 wencai | ~159 |
| kline 每日增量 | ~4550 | ~5016 |

⚠️ 门控：行业+概念共 466 次/日（用户 2026-08-28 确认方案 A）。仅行业时 91 次。

---

## 4. 数据源可用性（2026-08-27 实测）

| 接口 | 状态 | 用途 |
|------|------|------|
| 新浪 `ak.stock_zh_a_daily` | ✅ | kline 全量拉取（限速 0.15s/次） |
| 新浪 `ak.stock_sector_spot('概念')` | ✅ | 概念板块当日（1 次拿 175 个） |
| 新浪 `ak.stock_sector_spot('行业')` | ✅ | 行业板块当日 |
| 问财（Selenium） | ✅ | 当日个股筛选（慢，20-30s/次） |
| 东财 `*_em` 系列 | ❌ | 限流封禁（RemoteDisconnected），勿用 |
| baostock | ❌ | 登录卡死，勿用 |
| THS `industry_index_ths` | ✅ | merge_board_daily.py 在用；**涨幅自算（相邻收盘价），不信用 summary 快照**；保存前 stale 检测（相邻日 identical≥90% 拒绝写入） |

---

## 5. 关键脚本

### 每日必跑

| 脚本 | 作用 |
|---|---|
| `scripts/db_backfill_top3.py` | 行业口径回算 Top3 历史（行业Top3 × industry_members × kline>8%），纯本地 |
| `scripts/db_sync_today.py` | v4 Excel Sheet4/5/6/7 → DB（幂等，先删后插） |
| `scripts/db_html.py` | DB → HTML（7 tab，315 KB） |

### 一次性/维护

| 脚本 | 作用 |
|---|---|
| `backfill_ths_range.py` | 板块区间重抓（`python backfill_ths_range.py 行业|概念`，每板块 1 次调用） |
| `fetch_industry_members.py` | 刷新 THS 行业成分（问财 90 次，季度一次） |
| `crawler_all_concepts.py` | 刷新 THS 概念（F10，4线程防限流，月度一次） |
| `crawler_industry.py` | 抓申万三级（F10 field.html，月度一次） |
| `scripts/kline_full_pull.py` | 全量 K线拉取（新浪源，4575 只，~1小时；断点续跑自动跳过已有） |
| `scripts/db_import_macd_history.py` | 从备份 v4 导入 16 日 MACD 历史（已执行） |
| `scripts/db_fix_board_name.py` | 规范化概念名匹配回填（去括号/后缀/子串模糊） |
| `scripts/db_backfill_history.py` | kline 重算历史非Top3 >6% |
| `scripts/db_backfill_board.py` | non_top3 概念板块回填 |
| `scripts/db_schema_v2.py` | 建 top3/non_top3 表 |

### 已退役（DEPRECATED，跑则 exit）

- `sheet6_macd_roll_10d.py`（MACD v2 滚动 + 衍生 sheets）
- `inject_macd_tab.py`（MACD 滚动 tab 注入）
- `excel_to_html.py`（旧 HTML 生成器，被 db_html.py 取代）

---

## 6. HTML 看板说明（db_html.py）

**输出**：`data/每日复盘看板.html`（7 tab）

| Tab | 数据源 | 涂色逻辑 |
|---|---|---|
| 行业板块 Top10 | board_history(行业) | 10日内出现>2次且涨幅>1%超2次 → 固定色 + 顶部涨幅合计>10%汇总 |
| 概念板块 Top10 | board_history(概念) | **10日内出现>1次即涂色**（26个）+ 合计汇总 |
| 色卡图例 | 统计 | 出现次数分级色 |
| 每日Top3强势个股 | top3_stocks | **行业**Top3板块 × 个股>8%；wencai真实数据优先，历史由 db_backfill_top3 回算 |
| 非Top3板块强势个股 | non_top3_stocks | **10日内出现>2次的个股固定色** + 顶部重复个股列表 |
| MACD 5日>10% | macd_signals(5d_10pct) | 日期筛选，16日历史 |
| MACD 10日>20% | macd_signals(10d_20pct) | 日期筛选 |

---

## 7. 常见问题

### Q1: Top3 个股历史显示 "—"？
当日 wencai 有真实数据；历史日期由 `db_backfill_top3.py` 回算（**行业**Top3×industry_members×kline>8%）。某日无 >8% 个股是正常情况（如防御日）。

### Q2: 非Top3 概念列为空？
`db_fix_board_name.py` 规范化回填。仍为空的股票 = concept_data（6/17抓取）里没有，或概念名两套口径差异太大。新股需重爬 concept_data。

### Q3: kline 缺当日数据？
跑 `scripts/kline_full_pull.py`（幂等，只拉缺的）。东财源被限流，勿改回 stock_zh_a_hist。

### Q4: 概念板块当日没数据？
跑 `python merge_board_daily.py --include-concept`（9:15 前自动算上一交易日；含 stale 门禁）。

### Q5: DuckDB 被锁？
DuckDB 单写者模型。找占锁进程：`Get-Process python`，确认不是正在跑的拉取任务后 `Stop-Process -Id <pid> -Force`。

### Q6: 想看 16 日 MACD 历史？
`macd_signals` 表已有 2026-08-03 起的历史（从备份 v4 导入）。HTML 的 MACD tab 用日期筛选查看。

### Q7: 相邻两天板块涨幅完全一样？
THS 旧值 bug（2026-08-27 踩过）。merge_board_daily 已有 check_stale 门禁拦截；若 DB 已污染，用 `backfill_ths_range.py` 重抓该区间。

### Q8: 概念口径（已解决，方案 A）
概念当日数据统一走 `merge_board_daily.py --include-concept`（THS 375，自算 pct + stale 门禁）。
`db_import_concepts_spot.py` 已退役（新浪口径，会污染 board_history，脚本已加 guard）。

---

## 8. 改进历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v1.0 | 2026-07 | 初始（5 步流程） |
| v2.0-v2.4 | 2026-08-24~26 | 健康检查/数据验证/9:15 规则/问财列名修复 |
| v3.0 | 2026-08-27 | **DB 先行架构：DuckDB 唯一真相；HTML 从 DB 生成（db_html.py）；Sheet9-18 删除；Top3 改概念口径（历史可回算）；kline 全量入库（4571 只新浪源）；概念板块 1 次 akshare；MACD 16 日历史入库** |
| v3.1 | 2026-08-28 | merge_board_daily.py：行业 pct 改自算（修复 THS 旧值坑）+ check_stale 门禁；新增 backfill_ths_range.py（区间重抓工具）；8/1-8/27 全量重抓 + 8/25 回补 |
| v3.2 | 2026-08-28 | **Top3 改行业口径**（industry_members 90 行业）；新增 board_members/stock_industry_sw + db_import_members.py；DATA_DICTIONARY.md；概念/申万爬虫（F10） |

---

## 9. cron 自动化

**任务**：`MACD滚动筛选每日更新`（每天 16:00）
**注意**：cron payload 仍是旧流程（sheet6_macd_roll_10d 已废弃）。**建议更新为**：
```
merge_board_daily.py [--include-concept] → db_update.py --module board →
sheet5_wencai_v2.py → sheet6_wencai.py → sheet6_macd_chan_10d.py →
db_sync_today.py → db_backfill_top3.py → db_html.py
```
另建议改到 16:30+（收盘数据更稳，避开 THS 盘中旧值窗口）。
