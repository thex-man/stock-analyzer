# -*- coding: utf-8 -*-
"""
Multi-threaded fetcher for 同花顺 theme_key_points API
Fetches 题材要点 for all stocks in D:/stock/tool/stock/concept_data/
然后写回原JSON文件，追加 theme_points 字段
"""
import os
import json
import requests
import time
import glob
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ==== 配置 ====
CONCEPT_DIR = r'D:\stock\tool\stock\concept_data'
OUTPUT_DIR = r'D:\stock\tool\stock\concept_data_theme_points'
API_BASE = 'https://basic.10jqka.com.cn/fuyao/f10_stock_index/concept/v1'
THREADS = 16
BATCH_SIZE = 100  # 每批打印进度
TIMEOUT = 15
DELAY_BETWEEN_BATCHES = 0.5  # 批次间延迟，避免限流

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://basic.10jqka.com.cn/',
}

# ==== 市场判断 ====
def get_market_id(stock_code):
    """根据股票代码判断市场ID: 6开头=上海(1), 0/3/4开头=深圳(33)"""
    code = stock_code.strip()
    if code.startswith('6'):
        return '1'   # 上海
    elif code.startswith('8') or code.startswith('4'):
        return '43'  # 北交所
    else:
        return '33'  # 深圳

# ==== 获取单只股票的theme_points ====
def fetch_theme_points(stock_code, stock_name, market_id=None):
    """调用API获取单只股票的题材要点"""
    if market_id is None:
        market_id = get_market_id(stock_code)
    subject = f'{market_id}-{stock_code}'
    url = f'{API_BASE}/theme_key_points?subject={subject}'
    
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return {'stock_code': stock_code, 'stock_name': stock_name, 
                    'market_id': market_id, 'success': False, 
                    'error': f'HTTP {r.status_code}', 'points': []}
        
        data = r.json()
        if data.get('status_code') == 0 and data.get('data'):
            points = []
            for item in data.get('data', []):
                points.append({
                    'title': item.get('title', ''),
                    'content': item.get('content', ''),
                    'update_date': item.get('update_date', ''),
                    'summary': item.get('content', '')[:200] if item.get('content') else '',
                })
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'market_id': market_id,
                'success': True,
                'points': points,
                'fetch_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            }
        else:
            return {'stock_code': stock_code, 'stock_name': stock_name,
                    'market_id': market_id, 'success': False,
                    'error': 'no_data', 'points': []}
    except Exception as e:
        return {'stock_code': stock_code, 'stock_name': stock_name,
                'market_id': market_id, 'success': False,
                'error': str(e), 'points': []}

# ==== 更新单个JSON文件 ====
def update_concept_file(file_path, theme_result):
    """将theme_points追加到概念JSON文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 添加/更新 theme_points 字段
        data['theme_points'] = theme_result.get('points', [])
        data['theme_points_fetch_time'] = theme_result.get('fetch_time', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        data['theme_points_success'] = theme_result.get('success', False)
        
        # 保存回原文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        return False

# ==== 单文件处理函数 ====
def process_file(file_path):
    """处理单个概念文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        stock_code = data.get('stock_code', '')
        stock_name = data.get('stock_name', '')
        
        if not stock_code:
            return {'file': os.path.basename(file_path), 'success': False, 
                    'error': 'no_stock_code'}
        
        market_id = get_market_id(stock_code)
        theme_result = fetch_theme_points(stock_code, stock_name, market_id)
        update_concept_file(file_path, theme_result)
        
        return {
            'file': os.path.basename(file_path),
            'stock_code': stock_code,
            'stock_name': stock_name,
            'success': theme_result.get('success', False),
            'points_count': len(theme_result.get('points', [])),
            'error': theme_result.get('error', ''),
        }
    except Exception as e:
        return {'file': os.path.basename(file_path), 'success': False, 'error': str(e)}

# ==== 测试模式：只处理3只股票 ====
def test_mode():
    """测试模式：只取3只股票验证"""
    print('=== 测试模式：取3只股票 ===\n')
    
    # 找3只不同市场的股票
    test_files = []
    seen_codes = set()
    
    for fpath in glob.glob(os.path.join(CONCEPT_DIR, '*_concepts.json')):
        fname = os.path.basename(fpath)
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            code = data.get('stock_code', '')
            if code and code not in seen_codes and len(test_files) < 3:
                seen_codes.add(code)
                test_files.append((fpath, code, data.get('stock_name', '')))
                print(f'测试股票: {code} {data.get("stock_name", "")}')
        except:
            pass
    
    results = []
    for fpath, code, name in test_files:
        mkt = get_market_id(code)
        print(f'\n正在获取: {code} {name} (市场:{mkt})')
        result = fetch_theme_points(code, name, mkt)
        print(f'  成功: {result["success"]}, 要点数: {len(result.get("points", []))}')
        if result.get('points'):
            for pt in result['points']:
                print(f'  - {pt["title"]} ({pt["update_date"]})')
        results.append((fpath, result))
        
        # 更新文件
        update_concept_file(fpath, result)
    
    # 验证写入
    print('\n\n=== 验证写入 ===')
    for fpath, result in results:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        pts = data.get('theme_points', [])
        print(f'{data["stock_code"]}: theme_points count={len(pts)}, success={data.get("theme_points_success")}')
    
    return results

# ==== 全量模式 ====
def full_mode():
    """全量模式：16线程处理所有文件"""
    all_files = glob.glob(os.path.join(CONCEPT_DIR, '*_concepts.json'))
    total = len(all_files)
    print(f'全量模式启动: 共 {total} 个文件, {THREADS} 线程\n')
    
    success_count = 0
    fail_count = 0
    zero_count = 0
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        future_to_file = {executor.submit(process_file, fp): fp for fp in all_files}
        
        for i, future in enumerate(as_completed(future_to_file), 1):
            result = future.result()
            if result['success']:
                success_count += 1
                if result['points_count'] == 0:
                    zero_count += 1
            else:
                fail_count += 1
            
            if i % BATCH_SIZE == 0 or i == total:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / rate if rate > 0 else 0
                print(f'[{i}/{total}] 成功:{success_count} 失败:{fail_count} 无数据:{zero_count} 耗时:{elapsed:.1f}s 速度:{rate:.1f}/s 剩余:{eta:.0f}s')
            
            # 批次间小延迟，避免被限流
            if i % (BATCH_SIZE * THREADS) == 0:
                time.sleep(DELAY_BETWEEN_BATCHES)
    
    total_time = time.time() - start_time
    print(f'\n=== 完成 ===')
    print(f'总文件: {total}')
    print(f'成功: {success_count}, 失败: {fail_count}, 无数据: {zero_count}')
    print(f'总耗时: {total_time:.1f}s, 平均: {total/total_time:.2f}/s')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == '--full':
        full_mode()
    else:
        test_mode()
