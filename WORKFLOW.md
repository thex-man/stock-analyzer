# 今日复盘工作流 v1.1

> 触发词：**今日复盘** / **每日复盘** / **复盘**
>
> 每当用户说"今日复盘"时，自动执行以下步骤生成完整的每日复盘看板 HTML。

---

## 执行步骤

### Step 1 — 拉取今日板块数据

```bash
python daily_review.py --save --top 15
```

- 调用 akshare 获取**行业板块**和**概念板块**实时涨幅 Top15
- 输出：
  - `data/每日复盘_YYYYMMDD_HHMMSS.xlsx`（Excel，akshare 全量数据）
  - `data/每日复盘看板_YYYYMMDD_HHMMSS.html`（单日 HTML，仅行业+概念）

### Step 2 — 合并 Top3 强势个股到 v3 Excel

```bash
python add_top3_stocks_sheet.py
```

- 读取 `data/board_history_ths/history_*.json`（10日历史板块数据）
- 查询每天 Top3 板块成分股，筛选当日涨幅 >8% 的个股
- 写入 `data/板块轮动Top10_v3_含每日Top3强势个股.xlsx` → Sheet「每日Top3强势个股」
- **已移除背景涂色**（单元格仅保留边框+红色涨幅字体）

### Step 3 — 合并非 Top3 强势个股到 v4 Excel（pywencai）

```bash
python add_other_stocks_sheet.py
```

- **数据源：pywencai**（不是 baostock 遍历全A股）
- 流程：
  1. 用 pywencai 查近 10 日累计出现过的 Top3 板块（行业+概念合并去重）
  2. 对每个 Top3 板块用 pywencai 查「`<板块名>` 成份股 股票代码」拿成分股代码集合
  3. 用 pywencai 一次性查「`YYYY-MM-DD` 涨幅超过6% 股票代码 股票名称 涨跌幅 所属概念」
  4. 过滤掉在 Top3 板块成分股集合里的股票
  5. 写入 `data/板块轮动Top10_v4_含非Top3强势个股.xlsx` → Sheet「非Top3板块强势个股」
- **已移除背景涂色**
- **优势**：
  - 一次 pywencai 请求搞定，不用遍历 11099 只股票（之前 baostock 方案需 10-30 分钟）
  - 速度从 30 分钟压到秒级
- **依赖**：`pip install pywencai`

### Step 4 — 生成 Sheet6（MACD强势个股 5日>10%）

```bash
python sheet6_wencai.py
```

- 筛选条件：创业板（300xxx）+ MACD>0 + 近5日涨幅>10%
- 写 Sheet「MACD强势个股」到 v4 Excel

### Step 4.5 — 生成 Sheet7（MACD强势个股 10日>20%）— 必跑

```bash
python sheet6_macd_chan_10d.py
```

- 筛选条件：创业板（300xxx）+ MACD>0 + **近10日涨幅>20%**（比 Sheet6 更严格）
- K线来源：baostock（与 Sheet6 不同），需要 34 根以上 K 线
- 名称读取：`concept_data/{code6}_concepts.json` 中的 `stock_name` 字段
  - **踩坑**：`stock_name` 不是 `name`，曾被误读导致“名称”列填了代码
- 写 Sheet「MACD强势个股_10日」到 v4 Excel

> 必跑步骤：每次复盘都要生成 Sheet7，HTML 看板依赖它才能出现“10日>20%” tab。

### Step 5 — 生成完整复盘看板 HTML

```bash
python excel_to_html.py
```

- 读取 `data/板块轮动Top10_v4_含非Top3强势个股.xlsx`
- 生成 `data/每日复盘看板.html`（~368KB，含 Sheet6 + Sheet7 时）
- 包含 Sheet：行业板块 / 概念板块 / 色卡图例 / 每日Top3强势个股 / 非Top3板块强势个股 / MACD强势个股 / MACD强势个股_10日

---

## 输出文件

| 文件 | 说明 |
|------|------|
| `data/每日复盘看板.html` | 完整复盘看板（主要交付物） |
| `data/板块轮动Top10_v4_含非Top3强势个股.xlsx` | 含历史 + 今日数据的 Excel |
| `data/每日复盘_YYYYMMDD_HHMMSS.xlsx` | 当日原始数据备份 |

---

## 注意事项

- Step 1 → Step 5 顺序依赖：v2 (akshare) → v3 (Top3) → v4 (非Top3) → Sheet6 → Sheet7 → HTML
- `add_other_stocks_sheet.py` v1.1 默认走 pywencai，要求 iwencai 服务可达
- Step 5 依赖 v4 Excel 已有 Sheet 结构，若中间步骤失败需先修复
- Sheet7（10日>20%）为必跑，不可跳过

---

## 变更记录

### v1.1 (2026-08-22)
- **Step 3 切换到 pywencai**：从 baostock 全A股遍历改为 pywencai 一次查询
- 预计耗时：30 分钟 → 秒级

### v1.2 (2026-08-23)
- 新增 **Step 4.5**（必跑）：跑 `sheet6_macd_chan_10d.py` 生成 Sheet7（MACD强势个股_10日，10日涨幅>20%）
- HTML 看板新增独立 tab「MACD强势个股（10日>20%）」，复用 Sheet6 样式与配色
- 修 `sheet6_macd_chan_10d.py` 名称取值：原用 `cdata.get('name')`，概念 JSON 实际键为 `stock_name`，导致名称列填了代码；已改为 `cdata.get('stock_name') or cdata.get('name') or code6`
- v1.2 调整：Step 4.5 从可选升级为必跑（每次复盘都需要 Sheet7 数据）

### v1.0 (2026-08-22)
- 初始版本，4 步流水线（akshare + baostock + baostock + excel_to_html）

---

*工作流版本：v1.2 | 最后更新：2026-08-23 11:04*
