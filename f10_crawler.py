# -*- coding: utf-8 -*-
"""
THS F10 数据爬虫（events / profile / pledge / holders）
=====================================================
用法:
  python f10_crawler.py events   [--codes 300762,600519]   # 全市场或指定股票
  python f10_crawler.py profile
  python f10_crawler.py pledge
  python f10_crawler.py holders
断点续跑: f10_crawl_state 表记录已完成 (code,page)，重跑自动跳过（--force 忽略）。
4 线程 + 限速，防 THS 反爬。
入库表:
  stock_events(code, event_date, event_type, content, PK)
  stock_profile(code PK, main_business, products, controller, list_date, updated_at)
  stock_pledge(code PK, pledge_ratio, pledge_shares, pledge_holders, updated_at)
  stock_holders(code, period, rank, holder_name, shares, ratio, change, PK)
"""
import sys, io, re, time, json, argparse
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import duckdb

DB = r'D:\stock\tool\stock\data\stock.duckdb'
H = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
     'Accept-Language': 'zh-CN,zh;q=0.9', 'Referer': 'https://basic.10jqka.com.cn/'}
BASE = 'https://basic.10jqka.com.cn/{}/{}'


def get_html(code, page, gbk=True):
    for _ in range(3):
        try:
            r = requests.get(BASE.format(code, page), headers=H, timeout=15)
            if gbk:
                r.encoding = 'gbk'
            return r.text if r.status_code == 200 else None
        except Exception:
            time.sleep(3)
    return None


def strip_tags(s):
    s = s.replace('&nbsp;', ' ').replace('\xa0', ' ')
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', s)).strip()


# ---------- parsers ----------

def parse_events(code, html):
    """event.html -> [(date, type, content)]"""
    if not html:
        return []
    today = datetime.now().strftime('%Y-%m-%d')
    events = []
    for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', html, re.S):
        row = m.group(1)
        dm = re.search(r'<td class="hltip tc f12">(\d{4}-\d{2}-\d{2})</td>', row)
        if 'class="today' in row:
            date = today
        elif dm:
            date = dm.group(1)
        else:
            if not events:
                continue
            date = events[-1][0]   # rowspan 续行沿用上一日期
        tm = re.search(r'<strong class="hltip fl">([^：<]+)[：:]</strong>', row)
        if not tm:
            continue
        etype = tm.group(1).strip()
        sm = re.search(r'<span>(.*?)</span>', row, re.S)
        content = strip_tags(sm.group(1))[:500] if sm else ''
        if not content:
            cm = re.search(r'</strong>(.*?)</td>', row, re.S)
            content = strip_tags(cm.group(1))[:500] if cm else ''
        if content:
            events.append((date, etype, content))
    return events


def parse_profile(code, html_c, html_i):
    """company.html + index.html -> profile dict"""
    out = {'main_business': None, 'products': None, 'controller': None, 'list_date': None}
    if html_c:
        m = re.search(r'主营业务[：:]</strong>\s*<span>(.*?)</span>', html_c, re.S)
        if m:
            out['main_business'] = strip_tags(m.group(1))[:1000]
        m = re.search(r'产品名称[：:]</strong>\s*<span>(.*?)</span>', html_c, re.S)
        if m:
            out['products'] = strip_tags(m.group(1))[:500]
        m = re.search(r'实际控制人[^<]*</strong>?[^<]*<[^>]*>([^<]{2,30})<', html_c)
        if not m:
            m = re.search(r'控股股东[：:]</strong>\s*<[^>]*>([^<]{2,40})<', html_c)
        if m:
            out['controller'] = m.group(1).strip()
    if html_i:
        m = re.search(r'上市时间[：:]?\s*</span>\s*<span[^>]*>(\d{4}-\d{2}-\d{2})', html_i)
        if m:
            out['list_date'] = m.group(1)
    return out


def parse_pledge(code, html_cap, html_i):
    """capital.html 质押解冻 + index 摘要 -> pledge dict"""
    out = {'pledge_ratio': None, 'pledge_shares': None, 'pledge_holders': None}
    src = html_cap or html_i or ''
    for m in re.finditer(r'(质押比例|股权质押)[^0-9]{0,40}([\d.]+)%', src):
        out['pledge_ratio'] = float(m.group(2))
        break
    for m in re.finditer(r'质押股数[^0-9]{0,20}([\d.]+)\s*(万股|亿股|股)', src):
        v = float(m.group(1))
        u = m.group(2)
        out['pledge_shares'] = int(v * (1e4 if u == '万股' else 1e8 if u == '亿股' else 1))
        break
    for m in re.finditer(r'(质押股东|质押方)[^0-9]{0,15}(\d+)\s*(家|人|名)', src):
        out['pledge_holders'] = int(m.group(2))
        break
    return out


def parse_holders(code, html):
    """holder.html 十大股东（全部报告期 ther_N）-> [(period, rank, name, shares, ratio, change)]"""
    if not html:
        return []
    i = html.find('id="tenholder"')
    if i < 0:
        return []
    seg = html[i:i + 120000]
    # 报告期日期: ther_N -> date
    periods = dict(re.findall(r'name="ther_(\d+)"[^>]*>\s*<a[^>]*>(\d{4}-\d{2}-\d{2})</a>', seg))
    rows = []
    for m in re.finditer(r'<div[^>]*id="ther_(\d+)"[^>]*>(.*?)</div>\s*(?=<div|</div>)', seg, re.S):
        pass  # 嵌套 div 不可靠，改用表格切分
    # 每个报告期一个 table，顺序对应 ther_N
    tables = re.findall(r'<table[^>]*>(.*?)</table>', seg, re.S)
    ther_tables = []
    for tb in tables:
        if '机构或基金名称' in tb or '股东名称' in tb:
            ther_tables.append(tb)
    for idx, tb in enumerate(ther_tables, 1):
        period = periods.get(str(idx), f'p{idx}')
        for m in re.finditer(r'<tr[^>]*>(.*?)</tr>', tb, re.S):
            cells = [strip_tags(c) for c in re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>', m.group(1), re.S)]
            if len(cells) >= 4 and cells[0] and '机构或' not in cells[0] and '股东名称' not in cells[0] and '持有数量' not in cells[0]:
                name = cells[0][:60]
                shares = cells[1][:20] if len(cells) > 1 else ''
                change = cells[2][:20] if len(cells) > 2 else ''
                ratio = cells[3][:12] if len(cells) > 3 else ''
                pledge = cells[4][:12] if len(cells) > 4 else ''
                rows.append((period, str(idx), name, shares, ratio, change + '/' + pledge))
    # 只保留每个 period 前 10
    seen = {}
    out = []
    for r in rows:
        seen[r[0]] = seen.get(r[0], 0) + 1
        if seen[r[0]] <= 10:
            out.append(r)
    return out


# ---------- DB ----------

def get_con():
    return duckdb.connect(DB)


def ensure_tables(con):
    con.execute("""CREATE TABLE IF NOT EXISTS stock_events (
        code VARCHAR, event_date VARCHAR, event_type VARCHAR, content VARCHAR,
        updated_at VARCHAR, PRIMARY KEY (code, event_date, event_type, content))""")
    con.execute("""CREATE TABLE IF NOT EXISTS stock_profile (
        code VARCHAR PRIMARY KEY, main_business VARCHAR, products VARCHAR,
        controller VARCHAR, list_date VARCHAR, updated_at VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS stock_pledge (
        code VARCHAR PRIMARY KEY, pledge_ratio DOUBLE, pledge_shares BIGINT,
        pledge_holders INTEGER, updated_at VARCHAR)""")
    con.execute("""CREATE TABLE IF NOT EXISTS stock_holders (
        code VARCHAR, period VARCHAR, rank_ VARCHAR, holder_name VARCHAR,
        shares VARCHAR, ratio VARCHAR, change_ VARCHAR, updated_at VARCHAR,
        PRIMARY KEY (code, period, rank_, holder_name))""")
    con.execute("""CREATE TABLE IF NOT EXISTS f10_crawl_state (
        code VARCHAR, page VARCHAR, updated_at VARCHAR, PRIMARY KEY (code, page))""")


PAGE_JOBS = {
    'events':  lambda c: [(c, 'event.html')],
    'profile': lambda c: [(c, 'company.html'), (c, 'index.html')],
    'pledge':  lambda c: [(c, 'capital.html'), (c, 'index.html')],
    'holders': lambda c: [(c, 'holder.html')],
}


def crawl_one(code, page, con=None):
    """抓取一只股票的一类数据，返回 (code, n_rows, err)"""
    try:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if page == 'events':
            rows = parse_events(code, get_html(code, 'event.html'))
            if rows is None:
                return code, 0, 'fetch_fail'
            con.executemany("INSERT OR REPLACE INTO stock_events VALUES (?,?,?,?,?)",
                            [(code, d, t, x, ts) for d, t, x in rows])
            return code, len(rows), None
        if page == 'profile':
            p = parse_profile(code, get_html(code, 'company.html'), get_html(code, 'index.html'))
            con.execute("INSERT OR REPLACE INTO stock_profile VALUES (?,?,?,?,?,?)",
                        (code, p['main_business'], p['products'], p['controller'], p['list_date'], ts))
            return code, 1, None
        if page == 'pledge':
            p = parse_pledge(code, get_html(code, 'capital.html'), get_html(code, 'index.html'))
            con.execute("INSERT OR REPLACE INTO stock_pledge VALUES (?,?,?,?,?)",
                        (code, p['pledge_ratio'], p['pledge_shares'], p['pledge_holders'], ts))
            return code, 1, None
        if page == 'holders':
            rows = parse_holders(code, get_html(code, 'holder.html'))
            con.execute("DELETE FROM stock_holders WHERE code=?", [code])
            con.executemany("INSERT INTO stock_holders VALUES (?,?,?,?,?,?,?,?)",
                            [(code, p, r, n, s, ra, ch, ts) for p, r, n, s, ra, ch in rows])
            return code, len(rows), None
    except Exception as e:
        return code, 0, str(e)[:80]
    return code, 0, 'unknown_page'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('page', choices=list(PAGE_JOBS))
    ap.add_argument('--codes', help='逗号分隔，默认全市场')
    ap.add_argument('--force', action='store_true', help='忽略已完成标记重抓')
    ap.add_argument('--threads', type=int, default=4)
    args = ap.parse_args()

    con = get_con()
    ensure_tables(con)
    if args.codes:
        codes = [c.strip() for c in args.codes.split(',') if c.strip()]
    else:
        codes = [r[0] for r in con.execute(
            "SELECT code FROM stock_meta ORDER BY code").fetchall()]
    if not args.force:
        done = {r[0] for r in con.execute(
            "SELECT code FROM f10_crawl_state WHERE page=?", [args.page]).fetchall()}
        codes = [c for c in codes if c not in done]
    print(f'[{args.page}] {len(codes)} to crawl', flush=True)

    ok = fail = total_rows = 0
    lock = __import__('threading').Lock()

    def worker(code):
        c2 = duckdb.connect(DB)
        try:
            ensure_tables(c2)
            n, err = None, None
            r = crawl_one(code, args.page, c2)
            code, n, err = r
            if err is None:
                c2.execute("INSERT OR REPLACE INTO f10_crawl_state VALUES (?,?,?)",
                           [code, args.page, datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
            c2.close()
            return code, n, err
        except Exception as e:
            try:
                c2.close()
            except Exception:
                pass
            return code, 0, str(e)[:80]

    with ThreadPoolExecutor(max_workers=args.threads) as ex:
        for i, fut in enumerate(as_completed({ex.submit(worker, c): c for c in codes}), 1):
            code, n, err = fut.result()
            if err:
                fail += 1
            else:
                ok += 1
                total_rows += n
            if i % 50 == 0 or i == len(codes):
                print(f'  [{i}/{len(codes)}] ok={ok} fail={fail} rows={total_rows}', flush=True)
            if i % 20 == 0:
                time.sleep(1)
    print(f'[{args.page}] DONE ok={ok} fail={fail} rows={total_rows}', flush=True)


if __name__ == '__main__':
    main()
