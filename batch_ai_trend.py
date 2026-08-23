# -*- coding: utf-8 -*-
"""AI大模型/科创板政策核心标的趋势校验"""
import sys
sys.path.insert(0, r'D:\stock\tool\stock')
from check_trend import check_stock_trend
import json
from pathlib import Path

# AI大模型/算力核心标的（聚焦有实质业务的）
codes = [
    # 明确有AI大模型/算力业务
    '002230',  # 科大讯飞
    '300229',  # 拓尔思
    '688256',  # 寒武纪
    '688787',  # 海天瑞声
    '688327',  # 云从科技
    '301369',  # 联动科技
    '603985',  # 恒润股份（智谱AI）
    '300418',  # 昆仑万维
    '300364',  # 中文在线
    '300058',  # 蓝色光标
    '300624',  # 万兴科技
    '601360',  # 三六零
    '002354',  # 天娱数科
    '688111',  # 金山办公
    '688256',  # 寒武纪
    '603019',  # 中科曙光
    '000977',  # 浪潮信息
    '603019',  # 中科曙光
    '000725',  # 京东方A
    '300496',  # 中科创达
    '300274',  # 阳光电源
    '688041',  # 海光信息
    '688582',  # 芯动联科
    '300752',  # 隆利科技
    '300033',  # 同花顺
    '600570',  # 恒生电子
    '603859',  # 能科科技
    '002410',  # 广联达
    '300378',  # 鼎捷数智
    '002439',  # 启明星辰
    '603232',  # 格尔软件
    '688588',  # 东方国信
    '300247',  # 京东健康
    '688023',  # 安恒信息
    '300624',  # 万兴科技
    '300678',  # 中科信息
    '002049',  # 紫光国微
    '300349',  # 金卡智能
    '300229',  # 拓尔思
]

# 去重
codes = list(dict.fromkeys(codes))

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

up.sort(key=lambda x: x['return_20d'], reverse=True)
down.sort(key=lambda x: x['return_20d'], reverse=True)

print(f'AI核心标的趋势扫描（共{len(codes)}只）')
print(f'上涨趋势: {len(up)} 只 [UP]')
print(f'下跌趋势: {len(down)} 只 [DOWN]')
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
