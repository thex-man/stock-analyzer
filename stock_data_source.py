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
import subprocess, os, requests, json, time, shutil
import pandas as pd
import akshare as ak
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

WC_DIR = r'C:\Users\s5631\AppData\Local\Programs\Python\Python313\Lib\site-packages\pywencai'
CHROME_BIN = r'C:\Program Files\Google\Chrome\Application\chrome.exe'

# ============ Selenium Chrome Driver 缓存（进程内复用）============
_selenium_driver = None
_selenium_profile_dir = None

def _get_selenium_driver():
    """获取或创建 Selenium Chrome Driver（headless，单例）"""
    global _selenium_driver, _selenium_profile_dir
    if _selenium_driver is not None:
        try:
            _selenium_driver.current_url  # 保活检查
            return _selenium_driver
        except Exception:
            try:
                _selenium_driver.quit()
            except Exception:
                pass
            _selenium_driver = None
            if _selenium_profile_dir and os.path.exists(_selenium_profile_dir):
                shutil.rmtree(_selenium_profile_dir, ignore_errors=True)
            _selenium_profile_dir = None

    profile_dir = rf'C:\Users\s5631\AppData\Local\Temp\wencai_sel_{int(time.time())}'
    os.makedirs(profile_dir, exist_ok=True)

    options = Options()
    options.binary_location = CHROME_BIN
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-software-rasterizer')
    options.add_argument('--window-size=1280,720')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.page_load_strategy = 'eager'
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36")
    prefs = {"profile.managed_default_content_settings.images": 2}
    options.add_experimental_option('prefs', prefs)
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    options.add_argument("--log-level=3")
    options.add_argument(f'--user-data-dir={profile_dir}')

    service = Service(log_path=os.devnull)
    driver = webdriver.Chrome(service=service, options=options)
    driver.set_page_load_timeout(20)

    _selenium_driver = driver
    _selenium_profile_dir = profile_dir
    return driver


def _close_selenium_driver():
    """关闭 Selenium Driver（全局清理）"""
    global _selenium_driver, _selenium_profile_dir
    if _selenium_driver:
        try:
            _selenium_driver.quit()
        except Exception:
            pass
        _selenium_driver = None
    if _selenium_profile_dir:
        shutil.rmtree(_selenium_profile_dir, ignore_errors=True)
        _selenium_profile_dir = None

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

# ============ 4. 问财接口（Selenium Headless）============
def wencai(query: str, page: int = 1, perpage: int = 50) -> dict:
    """
    用 Selenium Headless Chrome 访问问财，执行查询并提取结果。

    query: 搜索语句，如 '创业板 MACD大于0 近5日涨幅大于10%'
    perpage: 每页条数（问财实际最多返回200条）
    返回: {'columns': [...], 'datas': DataFrame, 'total': int}
          出错返回 {'error': str}
    """
    try:
        driver = _get_selenium_driver()
    except Exception as e:
        return {'error': f'Chrome启动失败: {e}'}

    try:
        # 打开首页
        driver.get('http://www.iwencai.com')
        time.sleep(5)

        # 找搜索 textarea（React Shadow DOM 渲染）
        ta = driver.execute_script(
            "return document.querySelector('textarea[placeholder*=\"筛选条件\"]') "
            "|| document.querySelector('textarea');"
        )
        if not ta:
            return {'error': '未找到搜索框 textarea'}

        # 输入查询并提交
        driver.execute_script("arguments[0].value = ''", ta)
        ta.send_keys(query)
        ta.send_keys(Keys.RETURN)

        # 等待结果页 URL 变化
        try:
            WebDriverWait(driver, 15).until(
                EC.url_contains('/screener/result')
            )
        except Exception:
            return {'error': f'等待结果页超时，当前URL: {driver.current_url}'}

        # 等表格渲染（React 动态加载）
        time.sleep(10)

        # 用 JS 提取表格数据
        raw = driver.execute_script("""
            let container = document.querySelector('#xuangu-view table-wrapper-content')
                || document.querySelector('#tableWrap')
                || document.querySelector('.table-wrap')
                || document.querySelector('[class*="table-wrapper"]')
                || document.querySelector('#content');
            if (!container) {
                // 兜底：找最大的 table
                let tables = document.querySelectorAll('table');
                let best = null;
                for (let t of tables) {
                    if (!best || t.querySelectorAll('tr').length > best.querySelectorAll('tr').length)
                        best = t;
                }
                container = best;
            }
            if (!container) return {error: 'no_table'};

            let trs = container.querySelectorAll('tr');
            let result = [];
            for (let tr of trs) {
                let cells = tr.querySelectorAll('td,th');
                result.push(Array.from(cells).map(c => c.innerText.trim()));
            }
            return {rows: result.length, data: result};
        """)

        if raw.get('error') or not raw.get('data'):
            return {'error': f"表格提取失败: {raw.get('error')}"}

        rows = raw['data']
        if not rows:
            return {'error': '结果为空', 'data': pd.DataFrame()}

        # 检查表头完整性：如果第一行列数远少于数据行，说明表头残缺
        # 用列位置映射（问财结果列位置固定）
        if len(rows) >= 2 and (len(rows[0]) < 5 or len(rows[0]) != len(rows[1])):
            # 表头残缺，根据 row[1] 的数据量推断列数，用位置作列名
            # 用第一行数据推断列数（跳过表头行）
            data_rows = rows[1:] if len(rows[0]) < 5 else rows
            num_cols = len(data_rows[0]) if data_rows else 0
            # 问财选股结果列顺序（对照实际数据行确认）：
            # 0=序号, 1=(空), 2=股票代码, 3=股票简称, 4=最新价, 5=涨跌幅, 6=成交额,
            # 7=换手率, 8=量比, 9=振幅, 10=流通市值, 11=市盈率, 12=所属板块
            pos_names = [
                '序号', '_blank', '股票代码', '股票简称', '最新价',
                '涨跌幅', '成交额', '换手率', '量比', '振幅',
                '流通市值', '市盈率', '所属板块'
            ]
            # 取前 num_cols 个列名
            header = pos_names[:num_cols]
            # 不指定 header=None，让 pandas 自动分配列名，再 rename
            df = pd.DataFrame(data_rows)
            rename = {i: n for i, n in enumerate(header) if i < len(header)}
            if rename:
                df = df.rename(columns=rename)
            if len(df.columns) < len(data_rows[0]):
                # 如果实际列数多于 pos_names，补齐列名
                for i in range(len(df.columns)):
                    if i not in rename:
                        rename[i] = f'_col_{i}'
                df = df.rename(columns=rename)
        else:
            header = rows[0]
            data_rows = rows[1:]
            df = pd.DataFrame(data_rows, columns=header)

        return {
            'columns': list(df.columns),
            'datas': df,
            'total': len(df)
        }

    except Exception as e:
        return {'error': str(e)}


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
