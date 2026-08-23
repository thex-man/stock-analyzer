# -*- coding: utf-8 -*-
import baostock as bs
import pandas as pd

bs.login()
rs = bs.query_history_k_data_plus('sz.399006',
    'date,code,open,high,low,close,volume,amount,pctChg',
    start_date='2026-06-01', end_date='2026-08-21',
    frequency='d', adjustflag='2')
data = []
while rs.error_code == '0' and rs.next():
    data.append(rs.get_row_data())
bs.logout()
df = pd.DataFrame(data, columns=['date','code','open','high','low','close','volume','amount','pctChg'])
df[['high','low','close','pctChg']] = df[['high','low','close','pctChg']].astype(float)

# Key levels
high = df['high'].max()
high_date = df.loc[df['high'].idxmax(), 'date']
low = df['low'].min()
low_date = df.loc[df['low'].idxmin(), 'date']
print(f'Period high: {high:.2f} on {high_date}')
print(f'Period low:  {low:.2f} on {low_date}')

# A wave range
a_range = high - low
print(f'\nA浪幅度: {a_range:.2f} 点')

# Fibonacci retracements of A
for pct in [0.382, 0.500, 0.618, 0.786]:
    level = high - a_range * (1 - pct)
    print(f'  {pct*100:.1f}% 回撤位: {level:.2f}  ({'+' if level > high else ''}{level-high:.2f} vs high)')

# Recent structure
print('\n--- 近期关键高低点 ---')
print(df[['date','high','low','close','pctChg']].tail(20).to_string(index=False))

# Find local swing highs/lows in recent period
recent = df[df['date'] >= '2026-07-01'].copy()
print('\n--- 7月以来每日数据 ---')
for _, row in recent.iterrows():
    print(f"  {row['date']}  O:{row['open']:.1f}  H:{row['high']:.1f}  L:{row['low']:.1f}  C:{row['close']:.1f}  {row['pctChg']:+.2f}%")
