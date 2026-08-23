# -*- coding: utf-8 -*-
"""
概念板块数据爬虫（10jqka同花顺）

功能：获取指定股票的概念列表（名称、龙头股、概念ID）
      以及概念归类原因（来自主站页面）

数据来源：
  1. concept.html (GBK) → 概念列表 + 龙头股 + 概念ID
  2. 主站页面 (UTF-8)  → 概念原因
"""

import sys
import io
import re
import time
import json
import os
import requests
from bs4 import BeautifulSoup
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

SAVE_DIR = r"D:\stock\tool\stock\concept_data"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://basic.10jqka.com.cn/',
}

def init_save_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)

def fetch(url, timeout=15, encoding=None):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if encoding:
            r.encoding = encoding
        else:
            r.encoding = r.apparent_encoding or 'utf-8'
        return r.text, r.status_code
    except Exception as e:
        print(f"[ERROR] {url} - {e}")
        return None, None

def extract_concepts_from_concept_page(html):
    """
    从 concept.html 提取概念列表
    格式: <a topStock="xxx" class="J_popLink" cid="12345" tag="概念名">
    """
    # 直接用正则提取 topStock + cid + tag 三合一
    pattern = r'<a\s+topStock="([^"]+)"[^>]+cid="(\d+)"[^>]+tag="([^"]+)"'
    matches = re.findall(pattern, html)
    
    concepts = []
    for top_stock, cid, tag in matches:
        # tag 可能是 "其他概念-xxx" 格式，取最后一段
        name = tag.split('-')[-1].strip()
        skip_words = ['添加', '编辑', '更多', '展开', '收起', '返回', '确定', '取消']
        if name and len(name) <= 20 and not any(w in name for w in skip_words):
            concepts.append({
                'name': name,
                'cid': cid,
                'top_stocks': top_stock,
                'reason': '',
                'source': 'concept_page'
            })
    
    # 去重（按 cid）
    seen_cids = set()
    unique = []
    for c in concepts:
        if c['cid'] not in seen_cids:
            seen_cids.add(c['cid'])
            unique.append(c)
    
    return unique

def extract_concept_reasons(html):
    """
    从主站页面提取概念原因
    格式: <dd class="tip"><span>概念名：</span>原因内容
    """
    soup = BeautifulSoup(html, 'html.parser')
    reasons = {}
    
    tip_dds = soup.find_all('dd', class_='tip')
    for dd in tip_dds:
        span = dd.find('span')
        if not span:
            continue
        
        span_text = span.get_text(strip=True)
        # 去掉冒号末尾
        if span_text.endswith('：'):
            concept_name = span_text[:-1]
        elif span_text.endswith(':'):
            concept_name = span_text[:-1]
        else:
            concept_name = span_text
        
        full_text = dd.get_text(strip=True)
        reason = re.sub(r'^[^：:]+[：:]', '', full_text, count=1).strip()
        
        if concept_name and reason:
            reasons[concept_name] = reason
    
    return reasons

def save_result(stock_code, concepts):
    """保存结果到 JSON 文件"""
    output = {
        'stock_code': stock_code,
        'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_concepts': len(concepts),
        'concepts': concepts
    }
    
    fname = os.path.join(SAVE_DIR, f"{stock_code}_concepts.json")
    with open(fname, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"[*] 结果已保存: {fname}")
    return fname

def main():
    init_save_dir()
    
    stock_code = "300128"
    if len(sys.argv) >= 2:
        stock_code = sys.argv[1]
    
    print(f"[*] 股票代码: {stock_code}")
    print(f"[*] 保存目录: {SAVE_DIR}")
    print()
    
    # 1. 抓取 concept.html (GBK编码) → 概念列表 + 龙头股
    print(f"[*] 步骤1: 抓取 concept.html (概念列表+龙头股)...")
    concept_url = f"https://basic.10jqka.com.cn/{stock_code}/concept.html"
    concept_html, code = fetch(concept_url, encoding='gbk')
    
    concepts = []
    if code == 200 and concept_html:
        concepts = extract_concepts_from_concept_page(concept_html)
        print(f"[OK] 提取到 {len(concepts)} 个概念")
    
    # 2. 抓取主站页面 (UTF-8) → 概念原因
    print(f"\n[*] 步骤2: 抓取主站页面 (概念原因)...")
    main_url = f"https://basic.10jqka.com.cn/{stock_code}/"
    main_html, code = fetch(main_url)
    
    reasons = {}
    if code == 200 and main_html:
        reasons = extract_concept_reasons(main_html)
        print(f"[OK] 提取到 {len(reasons)} 个概念原因")
    
    # 3. 合并原因到概念列表
    for c in concepts:
        name = c['name']
        if name in reasons:
            c['reason'] = reasons[name]
        elif name.startswith('MR') or name == 'BC电池':
            # 尝试不同的匹配方式
            for k, v in reasons.items():
                if name in k or k in name:
                    c['reason'] = v
                    break
    
    # 4. 打印结果
    print(f"\n[*] 共 {len(concepts)} 个概念:")
    print(f"{'='*60}")
    for i, c in enumerate(concepts, 1):
        reason_preview = c['reason'][:60] + '...' if len(c['reason']) > 60 else c['reason']
        top_preview = c['top_stocks'][:50] if c['top_stocks'] else '无'
        print(f"  {i:2d}. {c['name']}")
        if c['top_stocks']:
            print(f"      龙头股: {top_preview}")
        if c['reason']:
            print(f"      原因: {reason_preview}")
        else:
            print(f"      原因: (暂无)")
    
    # 5. 保存
    save_result(stock_code, concepts)
    print(f"\n[*] 完成!")

if __name__ == "__main__":
    main()