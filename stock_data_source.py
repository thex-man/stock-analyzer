"""
stock_data_source.py
====================
解决各数据源接口不通的问题：

1. akshare 个股K线  → 改用 stock_zh_a_hist_tx（腾讯源），替代不通的东方财富源
2. pywencai         → 直接调用原始 HTTP 接口，不走 pywencai 库（库本身有 bug）
3. akshare 板块      → 新浪源，一直通，正常用
4. baostock          → K线稳定，正常用

用法：
    from stock_data_source import get_kline, get_board
    get_kline('sz300534', start='20260801', end='20260820')  # 个股K线（腾讯）
    get_board('概念')   # 板块涨幅（新浪）
"""
import subprocess, os, requests, json
import pandas as pd
import akshare as ak

WC_DIR = r'C:\Users\s5631\AppData\Local\Programs\Python\Python313\Lib\site-packages\pywencai'

# ============ 1. 个股K线：腾讯接口（akshare） ============
def get_kline(code: str, start: str = '20200101', end: str = '20991231',
              adjust: str = 'qfq') -> pd.DataFrame:
    """
    获取个股日K线，来源：akshare stock_zh_a_hist_tx（腾讯源）
    code格式: 'sz300534' 或 'sh600519'
    adjust: 'qfq'(前复权) / 'hfq'(后复权) / ''(不复权)
    """
    df = ak.stock_zh_a_hist_tx(symbol=code, start_date=start, end_date=end, adjust=adjust)
    return df

# ============ 2. 指数K线：新浪接口（akshare） ============
def get_index_kline(code: str = 'sh000001', last: int = 250) -> pd.DataFrame:
    """
    获取指数日K线，来源：akshare stock_zh_index_daily（新浪源）
    """
    df = ak.stock_zh_index_daily(symbol=code)
    return df.tail(last).reset_index(drop=True)

# ============ 3. 板块涨幅：新浪接口（akshare） ============
def get_board(kind: str = '概念', top: int = 20) -> pd.DataFrame:
    """
    获取板块涨幅排行，来源：akshare stock_sector_spot（新浪源）
    kind: '概念' 或 '行业'
    返回 top N 条，按涨跌幅降序
    """
    df = ak.stock_sector_spot(indicator=kind)
    # 识别列名
    name_col = next((c for c in df.columns if any(k in str(c) for k in ['板块', '概念', '名称', '行业'])), None)
    pct_col = next((c for c in df.columns if any(k in str(c) for k in ['涨跌幅', '涨幅'])), None)
    if name_col and pct_col:
        df['_pct'] = pd.to_numeric(df[pct_col].astype(str).str.replace('%', '').str.replace(',', ''), errors='coerce')
        df = df.sort_values('_pct', ascending=False).head(top)
    return df

# ============ 4. 问财原始接口（绕过pywencai库） ============
def wencai(query: str, page: int = 1, perpage: int = 50) -> dict:
    """
    直接调用问财HTTP接口，返回原始JSON（字典）
    绕过 pywencai 库的 bug（condition=None 时直接返回None）

    query: 搜索语句，如 '今日概念板块涨幅排行'
    返回: {'columns': [...], 'datas': [...], 'total': ...}
    """
    # 生成token
    token = subprocess.run(
        ['node', os.path.join(WC_DIR, 'hexin-v.bundle.js')],
        capture_output=True, timeout=10
    ).stdout.decode().strip()

    payload = {
        'add_info': '{"urp":{"scene":1,"company":1,"business":1},"contentType":"json","searchInfo":true}',
        'perpage': str(perpage),
        'page': page,
        'source': 'Ths_iwencai_Xuangu',
        'log_info': '{"input_type":"click"}',
        'version': '2.0',
        'secondary_intent': 'stock',
        'question': query
    }

    headers = {
        'hexin-v': token,
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Content-Type': 'application/json',
        'Referer': 'http://www.iwencai.com',
    }

    url = 'http://www.iwencai.com/customized/chart/get-robot-data'
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    resp = r.json()

    # 解析表格数据
    try:
        answer = resp['data']['answer'][0]
        txt = answer['txt'][0]
        comp = txt['content']['components'][0]
        comp_data = comp['data']

        columns = comp_data['columns']
        datas = comp_data['datas']

        # 列名映射
        col_map = {}
        for c in columns:
            key = c.get('key') or c.get('label', '')
            index_name = c.get('index_name', key)
            col_map[key] = index_name

        # 构造DataFrame
        rows = []
        for row in datas:
            mapped = {col_map.get(k, k): v for k, v in row.items()}
            rows.append(mapped)

        df = pd.DataFrame(rows)
        return {
            'columns': list(df.columns),
            'datas': df,
            'total': len(df)
        }
    except (KeyError, IndexError, TypeError) as e:
        return {'error': str(e), 'raw': resp}


# ============ 5. baostock K线（稳定备选） ============
def get_kline_bs(code: str, start: str, end: str, adjust: str = '2') -> pd.DataFrame:
    """
    baostock K线接口（最稳定）
    code: 'sz.300534' 或 'sh.000001' 格式
    adjust: '2'=前复权 '1'=后复权 '0'=不复权
    """
    import baostock as bs
    lg = bs.login()
    rs = bs.query_history_k_data_plus(
        code,
        'date,open,high,low,close,volume',
        start_date=start,
        end_date=end,
        frequency='d',
        adjustflag=adjust
    )
    data = []
    while rs.next():
        data.append(rs.get_row_data())
    bs.logout()
    df = pd.DataFrame(data, columns=rs.fields)
    for col in ['open', 'high', 'low', 'close', 'volume']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


# ============ 测试 ============
if __name__ == '__main__':
    print("=" * 55)
    print("  数据源测试")
    print("=" * 55)

    # 1. 腾讯K线
    print("\n[1] 个股K线 (腾讯接口 akshare)")
    df = get_kline('sz300534', start='20260810', end='20260820')
    print(f"  {len(df)}行, 列:{list(df.columns)}")
    print(df.tail(3).to_string())

    # 2. 板块
    print("\n[2] 概念板块涨幅 (新浪接口 akshare)")
    df = get_board('概念', top=10)
    print(f"  {len(df)}行")
    name_col = next((c for c in df.columns if '板块' in str(c) and '_pct' not in c), None)
    pct_col = next((c for c in df.columns if '涨跌幅' in str(c) and '_pct' in c), None)
    if name_col and pct_col:
        for _, row in df.iterrows():
            print(f"  {row[name_col]:<20} {row[pct_col]:>+7.2f}%")

    # 3. 问财
    print("\n[3] 问财原始接口")
    result = wencai('今日涨幅前10股票')
    if 'error' not in result:
        df = result['datas']
        print(f"  总行数: {result['total']}")
        # 找关键列
        for col in ['股票简称', '最新价', '涨跌幅:前复权[20260820]']:
            if col in df.columns:
                print(f"\n  {col}:")
                print(df[col].head(10).to_string())
    else:
        print(f"  失败: {result['error']}")

    print("\n" + "=" * 55)
    print("  测试完成")
    print("=" * 55)
