# 双数据源板块复盘：akshare + baostock
import baostock as bs
import pandas as pd
import akshare as ak
import time

print("=" * 60)
print("  板块涨幅复盘（双数据源）")
print("=" * 60)

# ============ 1. akshare 新浪板块 ============
print("\n>>> [1/2] akshare 新浪板块 抓取中...")
try:
    # 概念板块
    df_gn = ak.stock_sector_spot(indicator="概念")
    # 行业板块
    df_hy = ak.stock_sector_spot(indicator="行业")
    print(f"    akshare 概念: {len(df_gn)} 条, 行业: {len(df_hy)} 条")
    ak_success = True
except Exception as e:
    print(f"    akshare 失败: {e}")
    df_gn = pd.DataFrame()
    df_hy = pd.DataFrame()
    ak_success = False

# ============ 2. baostock 板块 ============
print("\n>>> [2/2] baostock 板块 抓取中...")
bs.login()
bs_success = False
try:
    # baostock 用 query_stock_industry 拿行业分类，再手动计算涨幅
    rs = bs.query_stock_industry()
    rows = []
    while rs.next():
        rows.append(rs.get_row_data())
    df_bs_industry = pd.DataFrame(rows, columns=rs.fields)
    print(f"    baostock 行业数: {len(df_bs_industry)}")
    bs_success = True
except Exception as e:
    print(f"    baostock 失败: {e}")
    df_bs_industry = pd.DataFrame()

# 尝试获取 baostock 概念（如果有的话）
bs_gn_data = []
try:
    # baostock 没有直接的概念板块接口，但有证券列表
    # 用 query_hs300_stocks 等获取成分股信息作为替代
    rs = bs.query_stock_basic(code='sh.000001')
    basic_rows = []
    while rs.next():
        basic_rows.append(rs.get_row_data())
    print(f"    baostock 基本信息接口: {len(basic_rows)} 条")
except Exception as e:
    print(f"    baostock 基本接口: {e}")

bs.logout()

# ============ 3. 输出对比 ============
print("\n" + "=" * 60)
print("  输出：概念板块涨幅TOP20（akshare）")
print("=" * 60)

if ak_success and not df_gn.empty:
    # 找板块名和涨跌幅列
    name_col = None
    pct_col = None
    for c in df_gn.columns:
        c_str = str(c)
        if name_col is None and any(k in c_str for k in ['板块', '概念', '名称', '行业']):
            name_col = c
        if pct_col is None and any(k in c_str for k in ['涨跌幅', '涨幅']):
            pct_col = c

    if name_col and pct_col:
        df_gn['_pct_num'] = pd.to_numeric(df_gn[pct_col].astype(str).str.replace('%','').str.replace(',',''), errors='coerce')
        top20 = df_gn.nlargest(20, '_pct_num')
        print(f"  {'板块名':<22} {'涨跌幅':>8}")
        print(f"  {'-'*32}")
        for _, r in top20.iterrows():
            name = str(r[name_col])[:20]
            pct = r['_pct_num']
            print(f"  {name:<22} {pct:>+7.2f}%")

print("\n" + "=" * 60)
print("  输出：行业板块涨幅TOP20（akshare）")
print("=" * 60)

if ak_success and not df_hy.empty:
    name_col = None
    pct_col = None
    for c in df_hy.columns:
        c_str = str(c)
        if name_col is None and any(k in c_str for k in ['板块', '概念', '名称', '行业']):
            name_col = c
        if pct_col is None and any(k in c_str for k in ['涨跌幅', '涨幅']):
            pct_col = c

    if name_col and pct_col:
        df_hy['_pct_num'] = pd.to_numeric(df_hy[pct_col].astype(str).str.replace('%','').str.replace(',',''), errors='coerce')
        top20 = df_hy.nlargest(20, '_pct_num')
        print(f"  {'行业名':<22} {'涨跌幅':>8}")
        print(f"  {'-'*32}")
        for _, r in top20.iterrows():
            name = str(r[name_col])[:20]
            pct = r['_pct_num']
            print(f"  {name:<22} {pct:>+7.2f}%")

# ============ 4. baostock 行业汇总 ============
print("\n" + "=" * 60)
print("  输出：行业板块涨幅TOP20（baostock）")
print("=" * 60)

if bs_success and not df_bs_industry.empty:
    print("字段:", list(df_bs_industry.columns))
    print(f"  {'行业':<22} {'涨跌幅':>8}")
    print(f"  {'-'*32}")
    # 尝试找涨跌幅列
    pct_col = None
    name_col = None
    for c in df_bs_industry.columns:
        c_str = str(c)
        if name_col is None and any(k in c_str for k in ['industry', 'name', '行业']):
            name_col = c
        if pct_col is None and any(k in c_str for k in ['change', 'pct', '涨幅', '涨跌幅']):
            pct_col = c

    if pct_col and name_col:
        df_bs_industry['_pct_num'] = pd.to_numeric(df_bs_industry[pct_col].astype(str).str.replace('%','').str.replace(',',''), errors='coerce')
        top20 = df_bs_industry.nlargest(20, '_pct_num')
        for _, r in top20.iterrows():
            name = str(r[name_col])[:20]
            pct = r.get('_pct_num', 0)
            print(f"  {name:<22} {pct:>+7.2f}%")
    else:
        print("  (无法识别列)")
        print("  前5行:", df_bs_industry.head().to_string())
else:
    print("  (baostock 无板块数据)")

print("\n" + "=" * 60)
print("  数据来源说明")
print("=" * 60)
print("  akshare: 新浪实时板块接口（概念+行业）")
print("  baostock: query_stock_industry（行业分类，无涨跌幅排名）")
print("=" * 60)
