# -*- coding: utf-8 -*-
"""批量对64只MCU相关股做趋势校验"""
import sys
sys.path.insert(0, r'D:\stock\tool\stock')
from check_trend import check_stock_trend
import json
from pathlib import Path

# 64只MCU相关股
mcu_codes = [
    '000333','000559','000651','001287','001298','002049','002156','002180',
    '002405','002448','002456','002553','002669','002851','002881','002960',
    '002993','003021','300001','300005','300053','300077','300134','300183',
    '300184','300223','300279','300287','300327','300386','300455','300458',
    '300474','300484','300543','300671','300672','300735','300975','301013',
    '301099','301221','600060','600171','600198','600271','600460','600498',
    '600877','601633','603015','603068','603160','603178','603232','603236',
    '603290','603421','603501','603738','603893','603986','605111','920267'
]

base = Path(r'D:\stock\tool\stock\concept_data')
results = []

for code in mcu_codes:
    r = check_stock_trend(code)
    # 读名称
    f = base / f'{code}_concepts.json'
    name = ''
    if f.exists():
        try:
            j = json.loads(f.read_text(encoding='utf-8'))
            name = j.get('stock_name', '')
        except:
            pass
    results.append({**r, 'name': name})

# 按趋势分组
up_stocks = [r for r in results if r['trend'] == 'up']
down_stocks = [r for r in results if r['trend'] == 'down']
uncertain = [r for r in results if r['trend'] == 'uncertain']

up_stocks.sort(key=lambda x: x['return_20d'], reverse=True)

print(f'MCU相关股趋势扫描完成！')
print(f'上涨趋势: {len(up_stocks)} 只')
print(f'下跌趋势: {len(down_stocks)} 只')
print(f'数据不足: {len(uncertain)} 只')
print()
print('========== 上涨趋势股票（按20日涨幅排序）==========')
print(f'{"代码":<8} {"名称":<10} {"最新价":>8} {"20日涨幅":>10} {"5日涨幅":>8} {"趋势详情"}')
print('-' * 80)
for s in up_stocks:
    print(f'{s["code"]:<8} {s["name"]:<10} {s["latest_price"]:>8.2f} {s["return_20d"]:>+10.1f}% {s["return_5d"]:>+8.1f}%  {s["detail"]}')

print()
print('========== 下跌趋势股票 ==========')
for s in down_stocks:
    print(f'{s["code"]:<8} {s["name"]:<10} {s["latest_price"]:>8.2f} {s["return_20d"]:>+10.1f}% {s["return_5d"]:>+8.1f}%  {s["detail"]}')
