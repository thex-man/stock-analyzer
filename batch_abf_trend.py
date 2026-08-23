# -*- coding: utf-8 -*-
"""ABF载板/玻璃基板/先进封装核心标的趋势校验"""
import sys
sys.path.insert(0, r'D:\stock\tool\stock')
from check_trend import check_stock_trend
import json
from pathlib import Path

# 核心标的（去重后）
codes = [
    # 玻璃基板
    '002008','300088','300433','603773','300776',
    '300576','300476','300757','300786','600367','600714',
    # ABF载板
    '002436','002815','002938','300814','300903',
    '002916','603228','603936','301297',
    # 先进封装（CoWoS载板封装厂）
    '002156','002185','600584','603005',
    # 载板相关
    '000725','603186','600183',
    # 面板/玻璃
    '601636',
]

base = Path(r'D:\stock\tool\stock\concept_data')
results = []

for code in codes:
    r = check_stock_trend(code)
    f = base / f'{code}_concepts.json'
    name = ''
    if f.exists():
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
            name = j.get('stock_name', '')
        except:
            pass
    results.append({**r, 'name': name})

up = [r for r in results if r['trend'] == 'up']
down = [r for r in results if r['trend'] == 'down']
uncertain = [r for r in results if r['trend'] == 'uncertain']

up.sort(key=lambda x: x['return_20d'], reverse=True)
down.sort(key=lambda x: x['return_20d'], reverse=True)

print(f'核心标的趋势扫描（共{len(codes)}只）')
print(f'上涨趋势: {len(up)} 只 [UP]')
print(f'下跌趋势: {len(down)} 只 [DOWN]')
print(f'数据不足: {len(uncertain)} 只')
print()
print('========== 上涨趋势 ==========')
print(f'{"代码":<8} {"名称":<10} {"最新价":>8} {"20日":>8} {"5日":>8} 趋势')
print('-' * 65)
for s in up:
    print(f'{s["code"]:<8} {s["name"]:<10} {s["latest_price"]:>8.2f} {s["return_20d"]:>+7.1f}% {s["return_5d"]:>+7.1f}%  {s["detail"]}')

print()
print('========== 下跌趋势（已剔除）==========')
for s in down:
    print(f'{s["code"]:<8} {s["name"]:<10} {s["latest_price"]:>8.2f} {s["return_20d"]:>+7.1f}% {s["return_5d"]:>+7.1f}%  {s["detail"]}')
