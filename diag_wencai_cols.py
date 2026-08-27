# -*- coding: utf-8 -*-
"""
诊断问财爬虫的真实返回结构（不依赖 Selenium 结果缓存）
直接发 HTTP 请求，解析原始 HTML 表格列结构
"""
import re, requests

def wencai_raw_html(query, perpage=100):
    """直接发 HTTP 请求到问财，返回原始 HTML"""
    url = 'https://www.iwencai.com/stockpick/search'
    params = {
        'typed': '1',
        'prephrase': '1',
        'repeat-check': '1',
        'topstock': '1',
        'multientry': '1',
        'searchrule': '3',
        'mQuery': query,
        'page': '1',
        'perpage': str(perpage),
    }
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Referer': 'https://www.iwencai.com/stockpick/search',
    }
    try:
        r = requests.post(url, data=params, headers=headers, timeout=10)
        return r.text
    except Exception as e:
        return f'Error: {e}'

# 测试1：今日查询（不带日期）
html1 = wencai_raw_html('种植业与林业 涨跌幅排序', perpage=10)
print('测试1 - 今日（无日期）查询:')
print('  HTML长度:', len(html1))
# 找表格
table_match = re.search(r'<table[^>]*>(.*?)</table>', html1, re.DOTALL)
if table_match:
    print('  找到表格，长度:', len(table_match.group(1)))
else:
    print('  未找到表格')
    print('  前500字符:', html1[:500])

print()

# 测试2：带历史日期查询
html2 = wencai_raw_html('种植业与林业 20260824 涨跌幅排序', perpage=10)
print('测试2 - 历史日期(20260824)查询:')
print('  HTML长度:', len(html2))
table_match2 = re.search(r'<table[^>]*>(.*?)</table>', html2, re.DOTALL)
if table_match2:
    print('  找到表格，长度:', len(table_match2.group(1)))
else:
    print('  未找到表格')
    print('  前500字符:', html2[:500])
