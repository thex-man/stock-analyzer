# 每日复盘 SOP v2.0

> 最后更新：2026-08-24
> 触发词：今日复盘 / 每日复盘 / 当日复盘
> 关联：cron 任务 `MACD滚动筛选每日更新`（16:00，北京时间）

## 0. 前置条件

- A 股已收盘（工作日 15:00 后）
- 确认数据日期：用 `date` 或看板检查最后日期
- 工作目录：`D:\stock\tool\stock`

---

## 1. 调用次数预算（重要！超门控需用户确认）

| 步骤 | 行业 | 概念 | 累计 | 是否安全 |
|---|---|---|---|---|
| **Step -1 备份** | 0 | 0 | 0 | ✅ |
| **Step 0 拉缓存**（默认仅行业） | 1+90=**91** | 0 | 91 | ✅ |
| **Step 0 --include-concept** | 91 | **375** | 466 | ❌ **需确认** |
| **Step 1 Sheet1/2/3** | 0（读缓存） | 0 | 91 | ✅ |
| **Step 1.5 Sheet4** | 30 wencai | 同 | 121 | ⚠️ 略超 |
| **Step 2 复制 v3→v4** | 0 | 0 | 121 | ✅ |
| **Step 3 Sheet5** | 10 wencai + ~100 baostock | 同 | ~230 | ❌ 超 |
| **Step 4 Sheet6 MACD v1** | ~23 wencai | - | ~253 | ❌ 超 |
| **Step 4.5 Sheet7 MACD v2** | ~23 wencai | - | ~276 | ❌ 超 |
| **Step 5 HTML 生成** | 0 | 0 | 276 | ✅ |
| **Step 6 注入 MACD tab** | 0 | 0 | 276 | ✅ |

**说明**：
- baostock 是 SDK，但每次 `query_stock_industry` 是网络调用，按"100 次门控"规则计入
- wencai 每次 query 都计入
- akshare 的 `index_ths(symbol=...)` 每次 1 个板块，N 个板块 = N 次

**超出处理**：
- 拆分执行：先跑 Step 0/1/1.5/2，跑完一次再继续 3/4/4.5
- 跳过概念：跑 `merge_board_daily.py`（默认行为）
- 用户确认：超过门控必须先取得用户授权

---

## 2. 完整流程

### 🔒 Step -1：自动备份（必做）

```powershell
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
Copy-Item data\板块轮动Top10_v4_含非Top3强势个股.xlsx data\板块轮动Top10_v4_含非Top3强势个股.bak.$ts.xlsx
Copy-Item data\每日复盘看板.html data\每日复盘看板.bak.$ts.html
```

**说明**：
- `inject_macd_tab.py` 会自动备份看板到 `.bak`（首次）
- `excel_to_html.py` 也会备份（确认）
- v4 Excel 没有自动备份脚本，必须手动

---

### 📥 Step 0：拉新板块缓存（每日必跑）

```powershell
# 仅补行业（90 次，安全）
python merge_board_daily.py

# 指定日期（默认今天）
python merge_board_daily.py --date 20260824

# 行业+概念（466 次，超门控，需先告知用户）
python merge_board_daily.py --include-concept
```

**脚本行为**：
- 读取最新 `history_*.json`
- 1 次 `industry_summary_ths()` 拿 90 个行业当日涨跌幅
- 90 次 `industry_index_ths()` 拿每个行业当日收盘点位
- 默认跳过概念（提示需 `--include-concept`）
- 输出新缓存：`history_YYYYMMDD_YYYYMMDD.json` + meta

**为什么这步必要**：
- `board_top10_excel.py` 直接读最新缓存，没有刷新机制
- 缓存最后更新日 = 数据最后日期，缺一天就没数据

---

### 📊 Step 1：生成 Sheet1/2/3（行业+概念 Top10 + 色卡图例）

```powershell
python board_top10_excel.py
```

**说明**：
- 读取最新 `history_*.json`，取最近 10 天
- 输出 `板块轮动Top10_v2_行业概念分开.xlsx`（含 Sheet1=行业, Sheet2=概念, Sheet3=色卡）
- 仅读不调用网络（依赖 Step 0 拉的新缓存）

---

### 📈 Step 1.5：追加 Sheet4 每日 Top3 强势个股

```powershell
python add_top3_stocks_sheet.py
```

**脚本行为**：
- 读取 v2 + 最新缓存
- 问财查每个 Top3 板块的强势个股（>8%）
- 10 天 × 3 Top3 = ~30 次 wencai（缓存命中不算）
- 输出 `板块轮动Top10_v3_含每日Top3强势个股.xlsx`（含 Sheet4）

---

### 🔀 Step 2：合并到 v4（保留 MACD v2 sheet）

```powershell
python copy_v3_to_v4.py
```

**⚠️ 不能 `cp v3 v4`！**

v4 已经包含 MACD v2.0 的 18 个 sheet（`sheet6_macd_roll_10d.py` 的工作）：
```
MACD强势个股, MACD强势个股_10日,
MACD信号消失追踪_5日/10日,
MACD概念聚合_5日/10日,
MACD回测_5日/10日,
MACD强势个股_v2/10日_v2,
MACD上榜频次_5日/10日,
_chart_data
```

直接 `cp` 会**覆盖整个文件**，MACD v2 数据全部丢失。

**脚本行为**：
1. 加载 v3 和 v4
2. 删除 v4 的 Sheet1-4（旧的）
3. 从 v3 复制 Sheet1-4（含内容/列宽/合并单元格）
4. 调整 sheet 顺序：Sheet1-5 在前
5. 保存 v4

---

### 🔍 Step 3：重建 Sheet5 非 Top3 强势个股

```powershell
python sheet5_wencai_v2.py
```

**脚本行为**：
- 直接打开 v4
- 删除并重建「非Top3板块强势个股」sheet
- 保留 v4 其他所有 sheet（含 MACD v2）
- 调用：10 wencai + ~100 baostock（按需补充个股行业分类）

---

### 📊 Step 4：MACD 强势个股 v1（5日>10%）

```powershell
python sheet6_wencai.py
```

**筛选条件**：创业板（300xxx）+ MACD>0 + 近5日涨幅>10%
**调用**：~23 wencai（22 只股票 + 1 次列表）
**输出**：v4 → Sheet6「MACD强势个股」（13 列）

---

### 📊 Step 4.5：MACD 强势个股 v2（10日>20%）

```powershell
python sheet6_macd_chan_10d.py
```

**筛选条件**：创业板 + MACD>0 + **近10日涨幅>20%**
**必跑**：HTML 看板依赖 Sheet7 才能出现 "10日>20%" tab
**调用**：~23 wencai
**输出**：v4 → Sheet7「MACD强势个股_10日」

---

### 🌐 Step 5：生成 HTML 看板

```powershell
python excel_to_html.py
```

**输出**：`data\每日复盘看板.html`（约 366KB）
**包含**：
- Sheet1/2：出现次数>2 且>2 次涨幅>1% → 涂色；合计>10% → 顶部汇总表
- Sheet4：个股出现>1次 → 涂色；汇总表按次数降序
- Sheet5：概念出现>1次 → 涂色；汇总表按次数降序
- Sheet6/7：按缠论分数排名，分数≥3 绿色、1~2 黄色、<0 红色

---

### 💉 Step 6：注入 MACD 滚动截面 tab（v2.0）

```powershell
python inject_macd_tab.py
```

**用途**：把 `reports\macd_latest.html` 注入到看板作为新 tab

**实现要点**：
- 使用 BeautifulSoup 精确操作 DOM（**不用正则**——之前踩过坑）
- CSS scope 限定在 `.macd-content` class（不影响看板全局）
- 首次自动备份看板到 `.bak`
- 删除旧 tab + 旧 panel，插入新的

**前置条件**：
- 已跑 `sheet6_macd_roll_10d.py` 生成 `reports\macd_latest.html`
- 此脚本不包含在 SOP 主流程（由 v2.0 工作流单独触发）

---

### 🔎 Step 7：验证（推荐）

```python
import openpyxl
wb = openpyxl.load_workbook('data/板块轮动Top10_v4_含非Top3强势个股.xlsx', data_only=True)
print(f'Sheets ({len(wb.sheetnames)}): {wb.sheetnames}')
ws = wb['行业板块']
print(f'行业最后日期: {ws.cell(row=ws.max_row, column=1).value}')
ws = wb['MACD强势个股_v2']
# 找今天的信号
for r in range(2, ws.max_row+1):
    if ws.cell(row=r, column=1).value == '2026-08-24':
        print(f'MACD v2 信号: {ws.cell(row=r, column=4).value}')
        break
```

---

## 3. 脚本文件清单

| 脚本 | 用途 | 调用次数 | 状态 |
|---|---|---|---|
| **merge_board_daily.py** | **Step 0 拉新缓存（v2.0 新增）** | 91 / 466 | **新建** |
| board_top10_excel.py | Step 1 Sheet1/2/3 | 0 | 已有 |
| add_top3_stocks_sheet.py | Step 1.5 Sheet4 | ~30 wencai | 已有 |
| **copy_v3_to_v4.py** | **Step 2 合并到 v4（v2.0 新增）** | 0 | **新建** |
| sheet5_wencai_v2.py | Step 3 Sheet5 | ~10 wencai + ~100 baostock | 已有 |
| sheet6_wencai.py | Step 4 Sheet6 v1 | ~23 wencai | 已有 |
| sheet6_macd_chan_10d.py | Step 4.5 Sheet7 | ~23 wencai | 已有 |
| excel_to_html.py | Step 5 HTML | 0 | 已有 |
| inject_macd_tab.py | Step 6 MACD tab | 0 | 已有 |

---

## 4. 数据源

### 板块历史缓存
- 路径：`D:\stock\tool\stock\data\board_history_ths\`
- 文件名：`history_YYYYMMDD_YYYYMMDD.json` + `meta_YYYYMMDD_YYYYMMDD.json`
- 结构：
  ```json
  {
    "贵金属": {
      "type": "行业",
      "data": [
        {"d": "20260821", "c": 5017.19, "p": 5.34},
        {"d": "20260824", "c": 6382.23, "p": 3.19}
      ]
    }
  }
  ```

### Excel 模板
- `data\板块轮动Top10_v4_含非Top3强势个股.xlsx`（18 个 sheet）

### 概念数据
- `concept_data\30xxxx.json` 等（6位代码为 key）
- THS F10 爬取（主板 2289 + 创业板 940 + 科创板 588 + 北交所 ~1871 ≈ 5688 只）

### 爬取脚本（按需运行）
- `crawler_kechuang_concepts.py`：科创板（688）
- `import_bj_concepts.py`：北交所（Excel → JSON）

---

## 5. 常见问题

### Q1: 行业有 8/24 但概念空？
**原因**：akshare 的 `concept_summary_ths()` 不是当日涨跌幅接口，只有 `industry_summary_ths()` 是。
**方案 A**：用 `concept_index_ths()` 逐板块调（375 次，**超门控**）
**方案 B**：等待东方财富 `concept_spot_em` 接口恢复（当前 RemoteDisconnected）
**当前默认**：跳过概念，仅补行业

### Q2: 调用超门控怎么办？
**拆分执行**：
- 第一批：Step -1/0/1/1.5/2（~121 次，**刚超**，需确认）
- 第二批：Step 3（~110 次）
- 第三批：Step 4/4.5（~46 次）
**降低预算**：
- 修改 `last_10` 为 `last_5`（减少天数 → 减少 wencai 调用）
- 缓存命中：重复日期走本地（不计入）

### Q3: MACD v2 sheet 被覆盖了？
**恢复备份**：
```powershell
$bak = Get-ChildItem data\板块轮动Top10_v4_含非Top3强势个股.bak.*.xlsx | Sort-Object Name -Descending | Select-Object -First 1
Copy-Item $bak.FullName data\板块轮动Top10_v4_含非Top3强势个股.xlsx
```

### Q4: sheet 顺序乱了？
跑 `copy_v3_to_v4.py` 自动调整前 5 个为 Sheet1-5。
如果仍不对，手动调：
```python
from openpyxl import load_workbook
wb = load_workbook('data/板块轮动Top10_v4_含非Top3强势个股.xlsx')
order = ['行业板块', '概念板块', '色卡图例', '每日Top3强势个股', '非Top3板块强势个股']
others = [n for n in wb.sheetnames if n not in order]
wb._sheets = [wb[n] for n in order + others]
wb.save('data/板块轮动Top10_v4_含非Top3强势个股.xlsx')
```

### Q5: 看板没显示 MACD tab？
1. 检查 `reports\macd_latest.html` 是否存在
2. 重跑 `inject_macd_tab.py`
3. 看 inject 日志，确认有"已插入新 tab 按钮"

---

## 6. 备注

### THS vs EM 数据源
- THS（同花顺）：`stock_board_*_index_ths` 单板块接口，akshare 的 THS summary 接口仅行业有
- EM（东方财富）：`*_spot_em` 一次返回所有，但当前 RemoteDisconnected（2026-08 测试）
- 当前主用 THS，EM 作 fallback

### 缓存策略
- 缓存增量合并：每次只补"昨日→今日"新数据，不重新拉全量
- K线缓存：`kline_cache/30xxxx_qfq.csv`（1399 个，13 分钟首次 + 30 秒缓存命中）

### 备份策略
- v4 Excel：手动备份（`Step -1`），文件名带时间戳
- HTML：自动备份（`inject_macd_tab.py` + `excel_to_html.py`）
- 缓存：每次保存为新文件名（`history_20260728_20260824.json`）

### 调用计数约定
- 命中本地缓存不计入
- 一次 HTTP 请求 = 1 次（不论返回数据量）
- baostock 的 `query_stock_industry` 算 1 次（虽然是 SDK）

---

## 7. 改进历史

| 版本 | 日期 | 改动 |
|---|---|---|
| v1.0 | 2026-07 | 初始版本（5 步：board_top10 → add_top3 → cp → sheet5 → excel_to_html） |
| v2.0 | 2026-08-24 | 新增 Step -1（备份）、Step 0（拉缓存）、Step 6（注入 MACD tab）；改 `cp` 为 `copy_v3_to_v4.py` 保留 MACD v2 sheet；调用次数预算说明；常见问题章节 |
