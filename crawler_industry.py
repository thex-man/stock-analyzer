# -*- coding: utf-8 -*-
"""
股票行业数据爬虫（10jqka F10 field.html）
=========================================
仿照 crawler_all_concepts.py：逐股抓 field.html，提取三级行业分类（申万口径）
静态 HTML，纯 requests。断点续跑：已存在 JSON 自动跳过。
产出: data/industry_data/{code}_industry.json
"""
import sys, io, re, time, json, os, openpyxl
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = r"D:\stock\tool\stock"
SAVE_DIR = os.path.join(BASE_DIR, 'data', 'industry_data')
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://basic.10jqka.com.cn/',
}
print_lock = threading.Lock()

# 三级行业分类：xx -- xx -- xx（共N家）
PAT = re.compile(r'三级行业分类：<span[^>]*>([^<]+?)（共<strong>(\d+)</strong>家）')
PAT2 = re.compile(r'所属申万行业：</span>\s*<span class="tip f14">([^<]+)</span>')


def crawl_stock(code):
    r = requests.get(f'https://basic.10jqka.com.cn/{code}/field.html',
                     headers=HEADERS, timeout=15)
    r.encoding = 'gbk'
    m = PAT.search(r.text)
    levels = []
    if m:
        levels = [x.strip() for x in m.group(1).split('--')]
    sw3 = levels[-1] if levels else None
    return {
        'stock_code': code,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'sw_l1': levels[0] if len(levels) >= 1 else None,
        'sw_l2': levels[1] if len(levels) >= 2 else None,
        'sw_l3': sw3,
        'sw_l3_members': int(m.group(2)) if m else None,
        'source': 'field.html',
    }


def worker(code):
    for attempt in (1, 2):
        try:
            return code, crawl_stock(code), None
        except Exception as e:
            if attempt == 2:
                return code, None, str(e)[:80]
            time.sleep(2)


def main():
    excel_path = os.path.join(BASE_DIR, 'stock_interactive_data', '全市场股票列表.xlsx')
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active
    stock_list = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code, name = row[0], row[1]
        if code and name:
            stock_list.append((str(code).zfill(6), str(name)))
    print(f'[*] 共 {len(stock_list)} 只股票', flush=True)
    os.makedirs(SAVE_DIR, exist_ok=True)

    todo = [(c, n) for c, n in stock_list
            if not os.path.exists(os.path.join(SAVE_DIR, f'{c}_industry.json'))]
    print(f'[*] 待抓 {len(todo)} 只（已有跳过）', flush=True)

    success, failed = 0, 0
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = {executor.submit(worker, c): (c, n) for c, n in todo}
        for i, future in enumerate(as_completed(futures), 1):
            code, result, err = future.result()
            if result:
                with open(os.path.join(SAVE_DIR, f'{code}_industry.json'), 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=1)
                success += 1
            else:
                failed += 1
            if i % 100 == 0 or i == len(todo):
                with print_lock:
                    print(f'[{i}/{len(todo)}] ok={success} fail={failed}', flush=True)
            if i % 50 == 0:
                time.sleep(1)

    print(f'[*] 完成: 成功 {success}, 失败 {failed}', flush=True)
    # 失败重跑一次（单线程温和重试）
    if failed:
        print('[*] 重试失败项...', flush=True)
        for c, n in stock_list:
            fp = os.path.join(SAVE_DIR, f'{c}_industry.json')
            if not os.path.exists(fp):
                try:
                    result = crawl_stock(c)
                    json.dump(result, open(fp, 'w', encoding='utf-8'), ensure_ascii=False)
                    time.sleep(0.5)
                except Exception:
                    pass
    print('[*] ALL DONE', flush=True)


if __name__ == '__main__':
    main()
