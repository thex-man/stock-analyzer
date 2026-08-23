# 每日复盘 SOP

## 触发词
今日复盘 / 每日复盘 / 当日复盘

## 数据源
- 板块历史缓存：`D:\stock\tool\stock\data\board_history_ths\history_*.json`（取最新）
- Excel 模板：`D:\stock\tool\stock\data\板块轮动Top10_v4_含非Top3强势个股.xlsx`
- 概念数据：`D:\stock\tool\stock\concept_data\`（JSON，key=6位代码）

### 概念数据来源（concept_data/）
| 市场 | 代码范围 | 来源 | 文件 |
|------|---------|------|------|
| 主板 | 6xx | 同花顺 F10 爬取 | `688xxx.json` 等 |
| 创业板 | 300 | 同花顺 F10 爬取 | `30xxxx.json` |
| 科创板 | 688 | 同花顺 F10 爬取 | `688xxx.json` |
| 北交所 | 4xx/8xx/83xx | `stock_data/beijiao_concepts.xlsx` 转换 | `43xxxx.json` 等 |

### 爬取脚本
- `crawler_kechuang_concepts.py`：爬取科创板（688）概念
- `import_bj_concepts.py`：将北交所 Excel 转换为 JSON
- 全量覆盖：主板 2289 + 创业板 940 + 科创板 588 + 北交所 ~1871 ≈ 5688 只

---

## Step 1 — 生成 Sheet1/2/4（行业板块、概念板块、每日Top3强势个股）

```powershell
cd D:\stock\tool\stock
python board_top10_excel.py           # 生成 Sheet1 行业Top10 + Sheet2 概念Top10
python add_top3_stocks_sheet.py      # 将 Sheet4（每日Top3强势个股）追加到 v3
# 若 v3 不存在，手动 copy v2 为 v3
```

**说明**：`board_top10_excel.py` 会生成 `板块轮动Top10_v2_行业概念分开.xlsx`。
`add_top3_stocks_sheet.py` 读取该 v2，追加 Sheet4，输出为 `板块轮动Top10_v3_含每日Top3强势个股.xlsx`。

---

## Step 2 — 构建 v4（含 Sheet4）

```powershell
# 方式A：直接 copy v3 为 v4
cp "data\板块轮动Top10_v3_含每日Top3强势个股.xlsx" "data\板块轮动Top10_v4_含非Top3强势个股.xlsx"

# 方式B（若 v3 不存在）：先生成 v3 再升级
python add_top3_stocks_sheet.py
cp "data\板块轮动Top10_v3_含每日Top3强势个股.xlsx" "data\板块轮动Top10_v4_含非Top3强势个股.xlsx"
```

---

## Step 3 — 生成 Sheet5（非Top3板块强势个股，含概念数据）

```powershell
python sheet5_wencai_v2.py
```

- 查询每日涨幅>6%且非Top3板块的个股，从 `concept_data/` 匹配"所属概念"
- 写入 `data\板块轮动Top10_v4_含非Top3强势个股.xlsx` Sheet5（6列：日期/代码/简称/所属概念/板块涨幅/个股涨幅）
- 输出 827 条记录

---

## Step 4 — 生成 Sheet6（MACD强势个股，创业板）

```powershell
python sheet6_wencai.py
```

- 数据源：`stock_data_source.wencai`（Node.js 生成 token，不走 pywencai 库）
- 筛选条件：创业板（300xxx）+ MACD>0 + 近5日涨幅>10%
- 缠论打分排序（分数高的在前，会涨的排前面）：
  - 底分型 +1.5 | 底背驰 +1.5 | 中枢上方强势 +2（强势离开再+1）
  - 上升趋势（20日>8%）+2 | 放量配合 +0.5
  - 顶分型/顶背驰扣分
- K线来源：`stock_data_source.get_kline`（akshare 腾讯源）
- 写入 `data\板块轮动Top10_v4_含非Top3强势个股.xlsx` Sheet6（13列）

## Step 4.5 — 生成 Sheet7（MACD强势个股 10日>20%，创业板）— 必跑

```powershell
python sheet6_macd_chan_10d.py
```

- 筛选条件：创业板（300xxx）+ MACD>0 + **近10日涨幅>20%**（比 Sheet6 更严格）
- K线来源：baostock（与 Sheet6 不同），需要 34 根以上 K 线
- 名称读取：`concept_data/{code6}_concepts.json` 中的 `stock_name` 字段
  - **踩坑**：`stock_name` 不是 `name`，曾被误读导致“名称”列填了代码
- 写入 `data\板块轮动Top10_v4_含非Top3强势个股.xlsx` Sheet7（**MACD强势个股_10日**，13列）
- 列结构与 Sheet6 一致，仅 F 列名称为 “10日涨幅%”（Sheet6 是 “5日涨幅%”）

> 必跑步骤：每次复盘都要生成 Sheet7，HTML 看板依赖它才能出现“10日>20%” tab。

## Step 5 — 生成 HTML 可视化看板

```powershell
python excel_to_html.py
```

- 读取 v4 Excel，生成 `data\每日复盘看板.html`（约 368KB，含 Sheet7 时）
- **Sheet1/2**：出现次数>2 且超过2次涨幅>1% → 涂色；涨幅合计>10% → 顶部汇总表（按合计降序）
- **Sheet4**：个股出现>1次 → 涂色；顶部汇总表（按次数降序，含出现日期）
- **Sheet5**：概念出现>1次 → 涂色；顶部汇总表（按次数降序，含出现日期）
- **Sheet6**：按缠论分数排名，分数>=3绿色、1~2黄色、<0红色；5日涨幅>20%标红
- **Sheet7**：与 Sheet6 同结构，只是涨幅阈值为 10日>20%
- Sheet4 日期合并单元格问题已修复（`current_date` 补全）

---

## 文件对应关系

| 文件 | 作用 |
|------|------|
| `board_top10_excel.py` | 生成 Sheet1 行业Top10 + Sheet2 概念Top10 |
| `add_top3_stocks_sheet.py` | 追加 Sheet4（每日Top3强势个股）→ v3 |
| `copy_v3_to_v4.py` | 复制 v3 → v4（临时用） |
| `sheet5_wencai_v2.py` | 生成 Sheet5（非Top3强势个股+概念）→ v4 |
| `sheet6_wencai.py` | 生成 Sheet6（MACD强势个股+缠论打分）→ v4 |
| `sheet6_macd_chan_10d.py` | 生成 Sheet7（MACD强势个股_10日，10日>20%）→ v4 |
| `sheet6_macd_chan.py` | Sheet6 本地版（baostock，目前未走 SOP） |
| `excel_to_html.py` | v4 Excel → HTML 看板（含 Sheet6 + Sheet7） |
| `crawler_kechuang_concepts.py` | 爬取科创板（688）概念 → `concept_data/688xxx.json` |
| `import_bj_concepts.py` | 将北交所 Excel → JSON → `concept_data/` |

## 输出

- Excel：`D:\stock\tool\stock\data\板块轮动Top10_v4_含非Top3强势个股.xlsx`
- HTML：`D:\stock\tool\stock\data\每日复盘看板.html`
- 概念缓存：`D:\stock\tool\stock\concept_data\`（key=6位代码，如 `688137.json`）

## 备注

- **THS 不支持北交所**：北交所概念数据来自已有的 `stock_data/beijiao_concepts.xlsx`，已转换存入 `concept_data/`
- **概念缓存 key 格式**：6位字符串，如 `'301080'`、`'688137'`、`'430017'`；读取时 `code.split('.')[0].zfill(6)`
- **概念缓存 name 字段**：JSON 中的股票名称键是 `stock_name`（不是 `name`），读错会 fallback 到代码
- **板块历史缓存**：`data/board_history_ths/history_*.json`，取最新日期文件
- **刷新概念数据**：重新运行 `crawler_kechuang_concepts.py`（688）和 `import_bj_concepts.py`（北交所）即可
