import baostock as bs
import pandas as pd

lg = bs.login()

rs = bs.query_history_k_data_plus(
    'sz.301008',
    'date,open,high,low,close,volume',
    start_date='2026-05-01',
    end_date='2026-08-20',
    frequency='d',
    adjustflag='2'
)
data = []
while rs.next():
    data.append(rs.get_row_data())
df = pd.DataFrame(data, columns=rs.fields)

# 转数值
for col in ['open','high','low','close','volume']:
    df[col] = df[col].astype(float)

dates = df['date'].tolist()
closes = df['close'].tolist()
opens = df['open'].tolist()
highs = df['high'].tolist()
lows = df['low'].tolist()
volumes = df['volume'].tolist()
n = len(df)

# ============ 基础行情 ============
def ma(arr, period):
    if len(arr) < period:
        return None
    return sum(arr[-period:]) / period

ma5 = ma(closes, 5)
ma10 = ma(closes, 10)
ma20 = ma(closes, 20)

change = (closes[-1] - closes[-2]) / closes[-2] * 100
change5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if n >= 6 else 0
change10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if n >= 11 else 0

vol_ma5 = sum(volumes[-5:]) / 5

print(f"{'='*55}")
print(f"  宏昌科技 (sz.301008)  行情")
print(f"{'='*55}")
print(f"  最新: {dates[-1]}  收盘 {closes[-1]:.2f}  涨跌 {change:+.2f}%")
print(f"  MA5: {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}")
print(f"  近5日涨幅: {change5:+.2f}%  近10日: {change10:+.2f}%")
print(f"  成交量: {volumes[-1]/10000:.0f}万手  量比: {volumes[-1]/vol_ma5:.2f}")
print(f"  最高: {highs[-1]:.2f}  最低: {lows[-1]:.2f}")

# ============ MACD ============
def calc_ema(series, period):
    ema = [series[0]]
    k = 2 / (period + 1)
    for price in series[1:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema

ema12 = calc_ema(closes, 12)
ema26 = calc_ema(closes, 26)
dif = [e12 - e26 for e12, e26 in zip(ema12, ema26)]
dea = calc_ema(dif, 9)
macd_bar = [(dif[i] - dea[i]) * 2 for i in range(n)]

print(f"\n--- MACD (近15日) ---")
print(f"  {'日期':<12} {'收盘':>7} {'DIF':>8} {'DEA':>8} {'MACD':>8}")
for i in range(n-15, n):
    bar = macd_bar[i]
    sign = "+" if bar > 0 else ""
    print(f"  {dates[i]:<12} {closes[i]:>7.2f} {dif[i]:>8.4f} {dea[i]:>8.4f} {sign}{bar:>7.4f}")

# ============ 缠论分型 ============
def get_fenxing(klines, direction):
    results = []
    for i in range(1, len(klines)-1):
        prev = klines[i-1]
        curr = klines[i]
        next_k = klines[i+1]
        if direction == 'top':
            if curr['high'] > prev['high'] and curr['high'] > next_k['high'] and curr['low'] > prev['low'] and curr['low'] > next_k['low']:
                results.append({'idx': i, 'day': curr['day'], 'high': curr['high'], 'low': curr['low'], 'type': 'top'})
        else:
            if curr['low'] < prev['low'] and curr['low'] < next_k['low'] and curr['high'] < prev['high'] and curr['high'] < next_k['high']:
                results.append({'idx': i, 'day': curr['day'], 'high': curr['high'], 'low': curr['low'], 'type': 'bottom'})
    return results

klines = [{'day': dates[i], 'open': opens[i], 'close': closes[i], 'high': highs[i], 'low': lows[i]} for i in range(n)]

tops = get_fenxing(klines, 'top')
bottoms = get_fenxing(klines, 'bottom')

# 合并异向分型
all_fx = [(t['idx'], t) for t in tops] + [(b['idx'], b) for b in bottoms]
all_fx.sort(key=lambda x: x[0])

filtered = []
last_dir = None
for idx, fx in all_fx:
    if last_dir is None:
        filtered.append((idx, fx))
        last_dir = fx['type']
    elif fx['type'] != last_dir:
        filtered.append((idx, fx))
        last_dir = fx['type']

print(f"\n{'='*55}")
print(f"  缠论结构")
print(f"{'='*55}")

# 全部关键分型
print(f"\n--- 分型 (近60日) ---")
recent_fx = [(idx, fx) for idx, fx in filtered if idx >= n - 60]
for idx, fx in recent_fx:
    label = "▲顶" if fx['type'] == 'top' else "▼底"
    print(f"  {fx['day']}  {label}  高:{fx['high']:.2f}  低:{fx['low']:.2f}")

# ============ 笔 ============
def find_bi(all_fx, min_bars=5):
    strokes = []
    if len(all_fx) < 2:
        return strokes
    last = all_fx[0]
    for i in range(1, len(all_fx)):
        idx, fx = all_fx[i]
        last_idx, last_fx = last
        if fx['type'] == last_fx['type']:
            continue
        bars_between = idx - last_idx
        if bars_between >= min_bars:
            strokes.append({
                'start_idx': last_idx,
                'end_idx': idx,
                'start_day': last_fx['day'],
                'end_day': fx['day'],
                'type': last_fx['type'],
                'start_p': last_fx['high'] if last_fx['type'] == 'top' else last_fx['low'],
                'end_p': fx['high'] if fx['type'] == 'top' else fx['low'],
                'start_high': last_fx['high'],
                'start_low': last_fx['low'],
                'end_high': fx['high'],
                'end_low': fx['low'],
            })
            last = all_fx[i]
    return strokes

recent_fx_60 = [(idx, fx) for idx, fx in filtered if idx >= n - 80]
strokes = find_bi(recent_fx_60, min_bars=5)

print(f"\n--- 笔 ---")
for s in strokes:
    bi_type = "↓下" if s['type'] == 'bottom' else "↑上"
    chg = s['end_p'] - s['start_p']
    chg_pct = chg / s['start_p'] * 100
    print(f"  {s['start_day']} ~ {s['end_day']} {bi_type}笔 {s['start_p']:.2f}→{s['end_p']:.2f} ({chg:+.2f}, {chg_pct:+.1f}%)")

# ============ 8月这波特殊走势 ============
print(f"\n{'='*55}")
print(f"  8月走势详解（涨停异动）")
print(f"{'='*55}")

print(f"\n--- 8月K线 ---")
print(f"  {'日期':<12} {'开':>7} {'收':>7} {'高':>7} {'低':>7} {'涨跌':>8} {'成交量(万)':>10}")
for i in range(n-25, n):
    if not dates[i].startswith('2026-08'):
        continue
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    arrow = "▲" if chg > 0 else "▼"
    print(f"  {dates[i]:<12} {opens[i]:>7.2f} {closes[i]:>7.2f} {highs[i]:>7.2f} {lows[i]:>7.2f} {arrow}{abs(chg):>6.2f}% {volumes[i]/10000:>10.0f}")

# 涨停分析
print(f"\n--- 涨停分析 ---")
for i in range(n-20, n):
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    if chg > 9.5:  # 涨停附近
        print(f"  {dates[i]}: 涨幅 {chg:+.2f}%, 开盘 {opens[i]:.2f}, 最高 {highs[i]:.2f}, 最低 {lows[i]:.2f}")
        if highs[i] == lows[i]:
            print(f"    → 一字涨停！")

# ============ 背驰判断 ============
print(f"\n--- 背驰判断 ---")
if len(strokes) >= 2:
    s1 = strokes[-2]
    s2 = strokes[-1]
    if s1['type'] == s2['type']:
        chg1 = abs(s1['end_p'] - s1['start_p'])
        chg2 = abs(s2['end_p'] - s2['start_p'])
        if s1['type'] == 'top':
            print(f"  下跌笔对比:")
            print(f"    笔{s1['start_day']}~{s1['end_day']}: {s1['start_p']:.2f}→{s1['end_p']:.2f} 跌幅={chg1:.2f}")
            print(f"    笔{s2['start_day']}~{s2['end_day']}: {s2['start_p']:.2f}→{s2['end_p']:.2f} 跌幅={chg2:.2f}")
            if chg2 < chg1:
                print(f"  → 背驰！本笔跌幅({chg2:.2f}) < 上一笔({chg1:.2f})")
            else:
                print(f"  → 无背驰")
        else:
            print(f"  上涨笔对比:")
            print(f"    笔{s1['start_day']}~{s1['end_day']}: {s1['start_p']:.2f}→{s1['end_p']:.2f} 涨幅={chg1:.2f}")
            print(f"    笔{s2['start_day']}~{s2['end_day']}: {s2['start_p']:.2f}→{s2['end_p']:.2f} 涨幅={chg2:.2f}")
            if chg2 < chg1:
                print(f"  → 背驰！本笔涨幅({chg2:.2f}) < 上一笔({chg1:.2f})，上涨动能衰竭")
            else:
                print(f"  → 无背驰")

# ============ 综合判断 ============
print(f"\n{'='*55}")
print(f"  综合判断")
print(f"{'='*55}")

trend = "上升" if ma5 > ma20 else "下降"
print(f"  1. 均线趋势: {trend} (MA5={ma5:.1f} > MA20={ma20:.1f})")
print(f"  2. 均线多空: {'多头排列' if ma5 > ma10 > ma20 else '混乱'}")
print(f"  3. MACD DIF: {dif[-1]:.4f} {'零轴上方' if dif[-1] > 0 else '零轴下方'}")

if strokes:
    ls = strokes[-1]
    print(f"  4. 最新笔: {ls['start_day']}~{ls['end_day']} {'↑上' if ls['type']=='top' else '↓下'}笔 {ls['start_p']:.2f}→{ls['end_p']:.2f}")

print(f"\n  关键位置:")
print(f"  · 涨停次日(8/10)低点: 35.32")
print(f"  · 8月最低: {min(lows[n-20:]):.2f}")
print(f"  · 8月最高: {max(highs[n-20:]):.2f}")
print(f"  · 当前: {closes[-1]:.2f}")

print(f"""
  结构判断:
  · 8/7 涨停(34.51→41.41)，是启动信号
  · 8/8~8/13 巨量换手(2000万手/日)，主力博弈剧烈
  · 8/14 回调到39.06，8/17~8/19 反弹到41~42
  · 目前在走 涨停后的中枢震荡 或 2浪回调

  后续观察:
  · 若站稳42+，可能走3浪主升
  · 若跌破39，可能走c浪，目标36~34
  · 量能是关键：需持续放量突破42才能确认启动
""")

bs.logout()
