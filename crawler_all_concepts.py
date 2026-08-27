# -*- coding: utf-8 -*-
"""
全市场股票概念数据爬虫 - 多线程版
"""
import sys, io, re, time, json, os, openpyxl
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE_DIR = r"D:\stock\tool\stock"
SAVE_DIR = r"D:\stock\tool\stock\data\concept_data"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://basic.10jqka.com.cn/',
}

# 进度锁
print_lock = threading.Lock()

def fetch(url, timeout=15, encoding=None):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.encoding = encoding or r.apparent_encoding or 'utf-8'
        return r.text, r.status_code
    except:
        return None, None

def extract_concepts_from_concept_page(html):
    pattern = r'<a\s+topStock="([^"]+)"[^>]+cid="(\d+)"[^>]+tag="([^"]+)"'
    matches = re.findall(pattern, html)
    concepts = []
    for top_stock, cid, tag in matches:
        name = tag.split('-')[-1].strip()
        skip_words = ['添加', '编辑', '更多', '展开', '收起', '返回', '确定', '取消']
        if name and len(name) <= 20 and not any(w in name for w in skip_words):
            concepts.append({'name': name, 'cid': cid, 'top_stocks': top_stock, 'reason': '', 'source': 'concept_page'})
    seen_cids = set()
    unique = []
    for c in concepts:
        if c['cid'] not in seen_cids:
            seen_cids.add(c['cid'])
            unique.append(c)
    return unique

def extract_concept_reasons(html):
    soup = BeautifulSoup(html, 'html.parser')
    reasons = {}
    for dd in soup.find_all('dd', class_='tip'):
        span = dd.find('span')
        if not span:
            continue
        span_text = span.get_text(strip=True)
        concept_name = span_text[:-1] if span_text.endswith(('：', ':')) else span_text
        full_text = dd.get_text(strip=True)
        reason = re.sub(r'^[^：:]+[：:]', '', full_text, count=1).strip()
        if concept_name and reason:
            reasons[concept_name] = reason
    return reasons

def crawl_stock(code, name):
    os.makedirs(SAVE_DIR, exist_ok=True)
    # v2: THS 高并发会返回空概念页，零命中重试3次
    concepts, reasons = [], {}
    for attempt in range(3):
        html1, code1 = fetch(f"https://basic.10jqka.com.cn/{code}/concept.html", encoding='gbk')
        concepts = extract_concepts_from_concept_page(html1) if code1 == 200 else []
        if concepts:
            break
        time.sleep(3 + attempt * 3)
    html2, code2 = fetch(f"https://basic.10jqka.com.cn/{code}/")
    reasons = extract_concept_reasons(html2) if code2 == 200 else {}
    for c in concepts:
        if c['name'] in reasons:
            c['reason'] = reasons[c['name']]
        else:
            for k, v in reasons.items():
                if c['name'] in k or k in c['name']:
                    c['reason'] = v
                    break
    return {
        'stock_code': code,
        'stock_name': name,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_concepts': len(concepts),
        'concepts': concepts
    }

def worker(code, name):
    """线程 worker，返回 (code, name, result_or_error)"""
    try:
        result = crawl_stock(code, name)
        return (code, name, result, None)
    except Exception as e:
        return (code, name, None, str(e))

def main():
    excel_path = os.path.join(BASE_DIR, 'stock_interactive_data', '全市场股票列表.xlsx')
    print(f"[*] 读取股票列表: {excel_path}")
    wb = openpyxl.load_workbook(excel_path)
    ws = wb.active

    stock_list = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        code, name = row[0], row[1]
        if code and name:
            stock_list.append((str(code).zfill(6), str(name)))

    print(f"[*] 共 {len(stock_list)} 只股票")
    os.makedirs(SAVE_DIR, exist_ok=True)

    success, skipped, failed = 0, 0, 0
    total = len(stock_list)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}
        for code, name in stock_list:
            fpath = os.path.join(SAVE_DIR, f"{code}_concepts.json")
            if os.path.exists(fpath):
                try:
                    with open(fpath, 'r', encoding='utf-8') as f:
                        _prev = json.load(f)
                    if _prev.get('total_concepts', 0) > 0:
                        with print_lock:
                            print(f"[{len(futures)+1}/{total}] 跳过 {code} {name} (已有{ _prev['total_concepts'] }个概念)")
                        skipped += 1
                        continue
                except Exception:
                    pass  # 损坏文件重抓
            future = executor.submit(worker, code, name)
            futures[future] = (code, name)

        done_count = 0
        for future in as_completed(futures):
            code, name = futures[future]
            done_count += 1
            ccode, cname, result, err = future.result()
            if result:
                fname = os.path.join(SAVE_DIR, f"{code}_concepts.json")
                with open(fname, 'w', encoding='utf-8') as f:
                    json.dump(result, f, ensure_ascii=False, indent=2)
                with print_lock:
                    print(f"[{done_count}/{total}] OK {code} {name} -> {result['total_concepts']} 个概念")
                success += 1
            else:
                with print_lock:
                    print(f"[{done_count}/{total}] FAIL {code} {name} -> {err}")
                failed += 1

            # 每20只休息一下（v2: 降低限流风险）
            if done_count % 20 == 0:
                time.sleep(2)

    print(f"\n[*] 完成: 成功 {success}, 跳过 {skipped}, 失败 {failed}")

    # 构建索引
    print(f"[*] 构建索引...")
    index = []
    for code, name in stock_list:
        fpath = os.path.join(SAVE_DIR, f"{code}_concepts.json")
        if os.path.exists(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                index.append({
                    'stock_code': code,
                    'stock_name': name,
                    'total_concepts': data.get('total_concepts', 0),
                    'concept_names': [c['name'] for c in data.get('concepts', [])]
                })
            except:
                index.append({'stock_code': code, 'stock_name': name, 'total_concepts': 0, 'concept_names': []})

    concept_map = defaultdict(list)
    for item in index:
        for cn in item['concept_names']:
            concept_map[cn].append({'code': item['stock_code'], 'name': item['stock_name']})

    index_fname = os.path.join(BASE_DIR, 'stock_interactive_data', 'index.json')
    with open(index_fname, 'w', encoding='utf-8') as f:
        json.dump(index, f, ensure_ascii=False, indent=2)
    print(f"[*] index.json ({len(index)} 条)")

    map_fname = os.path.join(BASE_DIR, 'stock_interactive_data', 'concept_stock_map.json')
    with open(map_fname, 'w', encoding='utf-8') as f:
        json.dump(dict(concept_map), f, ensure_ascii=False, indent=2)
    print(f"[*] concept_stock_map.json ({len(concept_map)} 个概念)")

    print(f"[*] 全部完成!")

if __name__ == "__main__":
    main()