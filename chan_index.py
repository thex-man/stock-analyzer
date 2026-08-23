import requests, json

# 获取上证指数(sh000001)日K线 - 最近250个交易日
url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
params = {'symbol': 'sh000001', 'scale': '240', 'ma': '5', 'datalen': '250'}
r = requests.get(url, params=params, timeout=10)
data = r.json()

dates = [d['day'] for d in data]
closes = [float(d['close']) for d in data]
opens = [float(d['open']) for d in data]
highs = [float(d['high']) for d in data]
lows = [float(d['low']) for d in data]
volumes = [int(d['volume']) for d in data]

n = len(data)
print(f"上证指数 K线数量: {n}根")

# ============ 基础行情 ============
def ma(arr, period):
    if len(arr) < period:
        return None
    return sum(arr[-period:]) / period

ma5 = ma(closes, 5)
ma10 = ma(closes, 10)
ma20 = ma(closes, 20)
ma60 = ma(closes, 60)
ma120 = ma(closes, 120) if len(closes) >= 120 else None

change = (closes[-1] - closes[-2]) / closes[-2] * 100
change5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if n >= 6 else 0
change10 = (closes[-1] - closes[-11]) / closes[-11] * 100 if n >= 11 else 0
change20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if n >= 21 else 0

vol_ma5 = sum(volumes[-5:]) / 5

print(f"\n{'='*50}")
print(f"  上证指数 (SH000001)  今日: {dates[-1]}")
print(f"{'='*50}")
print(f"  最新收盘: {closes[-1]:.2f}  涨跌: {change:+.2f}%")
print(f"  MA5:  {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}")
print(f"  MA60: {ma60:.2f}" + (f"  MA120: {ma120:.2f}" if ma120 else ""))
print(f"  近5日涨幅: {change5:+.2f}%  近10日: {change10:+.2f}%  近20日: {change20:+.2f}%")
print(f"  成交量: {volumes[-1]/10000:.0f}万手  量比(5日均量): {volumes[-1]/vol_ma5:.2f}")
print(f"  最高: {highs[-1]:.2f}  最低: {lows[-1]:.2f}")

# ============ 均线多空判断 ============
print(f"\n--- 均线多空 ---")
if ma5 > ma10 > ma20:
    print(f"  均线多头排列 (MA5>{ma5:.1f} > MA10>{ma10:.1f} > MA20>{ma20:.1f})")
elif ma5 < ma10 < ma20:
    print(f"  均线空头排列 (MA5<{ma5:.1f} < MA10<{ma10:.1f} < MA20<{ma20:.1f})")
else:
    print(f"  均线混乱排列")

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

print(f"\n--- MACD (近10日) ---")
print(f"  {'日期':<12} {'收盘':>7} {'DIF':>8} {'DEA':>8} {'MACD':>8}")
for i in range(n-10, n):
    bar = macd_bar[i]
    print(f"  {dates[i]:<12} {closes[i]:>7.2f} {dif[i]:>8.4f} {dea[i]:>8.4f} {bar:>8.4f}")

dif_latest = dif[-1]
dea_latest = dea[-1]
bar_latest = macd_bar[-1]
print(f"\n  DIF: {dif_latest:.4f}  DEA: {dea_latest:.4f}  MACD柱: {bar_latest:.4f}")
if dif_latest > dea_latest and bar_latest > 0:
    print(f"  → 金叉状态(多头)，MACD柱放大")
elif dif_latest < dea_latest and bar_latest < 0:
    print(f"  → 死叉状态(空头)，MACD柱收缩")
elif dif_latest > dea_latest and bar_latest < 0:
    print(f"  → DIF穿0轴后DEA上方运行")
else:
    print(f"  → 反弹状态，关注0轴压力")

# ============ 缠论分型 + 笔 + 线段 ============
print(f"\n{'='*50}")
print(f"  缠论分析")
print(f"{'='*50}")

def get_fenxing(klines, direction):
    """
    识别顶分型和底分型
    direction: 'top' 找顶分型, 'bottom' 找底分型
    """
    results = []
    i = 1
    while i < len(klines) - 1:
        prev = klines[i-1]
        curr = klines[i]
        next_k = klines[i+1]
        
        if direction == 'top':
            # 顶分型：中K线高点最高，低点也最高
            if curr['high'] > prev['high'] and curr['high'] > next_k['high'] and curr['low'] > prev['low'] and curr['low'] > next_k['low']:
                results.append({'idx': i, 'day': curr['day'], 'high': curr['high'], 'low': curr['low'], 'type': 'top'})
        else:
            # 底分型：中K线低点最低，高点也最低
            if curr['low'] < prev['low'] and curr['low'] < next_k['low'] and curr['high'] < prev['high'] and curr['high'] < next_k['high']:
                results.append({'idx': i, 'day': curr['day'], 'high': curr['high'], 'low': curr['low'], 'type': 'bottom'})
        i += 1
    return results

# 构建K线列表
klines = [{'day': dates[i], 'open': opens[i], 'close': closes[i], 'high': highs[i], 'low': lows[i]} for i in range(n)]

# 识别所有分型
tops = get_fenxing(klines, 'top')
bottoms = get_fenxing(klines, 'bottom')

print(f"\n近30日分型:")
print(f"  {'日期':<12} {'类型':>4} {'高点':>8} {'低点':>8}")

# 合并顶底（交替出现）
all_fenxing = []
for t in tops:
    all_fenxing.append((t['idx'], t))
for b in bottoms:
    all_fenxing.append((b['idx'], b))
all_fenxing.sort(key=lambda x: x[0])

# 过滤：只保留相邻异向分型
filtered = []
last_direction = None
for idx, fx in all_fenxing:
    if last_direction is None:
        filtered.append((idx, fx))
        last_direction = fx['type']
    elif fx['type'] != last_direction:
        filtered.append((idx, fx))
        last_direction = fx['type']

# 最近30日内的分型
recent_idxs = [idx for idx, _ in all_fenxing if idx >= n - 40]
if recent_idxs:
    min_idx = min(recent_idxs)
    recent_fenxing = [(idx, fx) for idx, fx in all_fenxing if idx >= min_idx]
    for idx, fx in recent_fenxing[-20:]:
        print(f"  {fx['day']:<12} {'顶分型' if fx['type']=='top' else '底分型':>4} {fx['high']:>8.2f} {fx['low']:>8.2f}")

# ============ 最近20根K线详细 ============
print(f"\n近20根K线:")
print(f"  {'日期':<12} {'开':>7} {'收':>7} {'高':>7} {'低':>7} {'涨跌幅':>8}")
for i in range(n-20, n):
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    arrow = "▲" if chg > 0 else "▼"
    print(f"  {dates[i]:<12} {opens[i]:>7.2f} {closes[i]:>7.2f} {highs[i]:>7.2f} {lows[i]:>7.2f} {arrow}{abs(chg):>6.2f}%")

# ============ 笔的识别 ============
print(f"\n--- 笔的识别 ---")
# 相邻同向分型之间如果超过5根K线（考虑包含关系后），可以构成一笔
# 简化：用分型间距判断笔

def find_bi(all_fenxing, min_bars=5):
    """根据分型识别笔"""
    strokes = []
    if len(all_fenxing) < 2:
        return strokes
    
    last = all_fenxing[0]
    for i in range(1, len(all_fenxing)):
        idx, fx = all_fenxing[i]
        last_idx, last_fx = last
        
        # 同向且间距>=min_bars
        if fx['type'] == last_fx['type']:
            continue
        
        bars_between = idx - last_idx
        if bars_between >= min_bars:
            strokes.append({
                'start_idx': last_idx,
                'end_idx': idx,
                'start_day': last_fx['day'],
                'end_day': fx['day'],
                'type': last_fx['type'],  # 起始分型的方向
                'start_p': last_fx['high'] if last_fx['type'] == 'top' else last_fx['low'],
                'end_p': fx['high'] if fx['type'] == 'top' else fx['low'],
            })
            last = all_fenxing[i]
    
    return strokes

# 只用最近60根K线分析笔
recent_fenxing_60 = [(idx, fx) for idx, fx in all_fenxing if idx >= n - 60]
strokes = find_bi(recent_fenxing_60, min_bars=5)

print(f"\n近60日笔 (共{len(strokes)}笔):")
for s in strokes:
    bi_type = "↓下笔" if s['type'] == 'bottom' else "↑上笔"
    change_p = s['end_p'] - s['start_p']
    change_pct = change_p / s['start_p'] * 100 if s['start_p'] != 0 else 0
    print(f"  {s['start_day']} ~ {s['end_day']} {bi_type} {s['start_p']:.2f}→{s['end_p']:.2f} ({change_p:+.2f}, {change_pct:+.1f}%)")

# ============ 背驰判断 ============
print(f"\n--- 背驰判断 ---")
# 找最近同向的两笔进行对比
if len(strokes) >= 2:
    s1 = strokes[-2]  # 上一笔
    s2 = strokes[-1]  #最近一笔
    
    # 笔2 vs 笔1力度对比
    if s1['type'] == s2['type']:
        # 同向笔背驰比较
        change1 = abs(s1['end_p'] - s1['start_p'])
        change2 = abs(s2['end_p'] - s2['start_p'])
        
        if s1['type'] == 'top':  # 向下笔：跌幅力度比较
            print(f"  下跌笔力度对比:")
            print(f"    笔{s1['start_day']}~{s1['end_day']}: {s1['start_p']:.2f}→{s1['end_p']:.2f} 跌幅={change1:.2f}")
            print(f"    笔{s2['start_day']}~{s2['end_day']}: {s2['start_p']:.2f}→{s2['end_p']:.2f} 跌幅={change2:.2f}")
            if change2 < change1:
                print(f"  → 背驰！本笔跌幅({change2:.2f})小于上一笔({change1:.2f})，下跌动能衰竭")
            else:
                print(f"  → 无背驰，本笔跌幅({change2:.2f})大于等于上一笔({change1:.2f})")
        else:  # 向上笔
            print(f"  上涨笔力度对比:")
            print(f"    笔{s1['start_day']}~{s1['end_day']}: {s1['start_p']:.2f}→{s1['end_p']:.2f} 涨幅={change1:.2f}")
            print(f"    笔{s2['start_day']}~{s2['end_day']}: {s2['start_p']:.2f}→{s2['end_p']:.2f} 涨幅={change2:.2f}")
            if change2 < change1:
                print(f"  → 背驰！本笔涨幅({change2:.2f})小于上一笔({change1:.2f})，上涨动能衰竭")
            else:
                print(f"  → 无背驰，本笔涨幅({change2:.2f})大于等于上一笔({change1:.2f})")
    else:
        print(f"  笔方向不同，无法直接对比背驰")

# ============ 缠论综合判断 ============
print(f"\n{'='*50}")
print(f"  综合判断")
print(f"{'='*50}")

# 1. 趋势判断
if ma5 > ma20:
    trend = "上升趋势"
elif ma5 < ma20:
    trend = "下降趋势"
else:
    trend = "震荡"

# 2. MACD状态
if dif_latest > 0 and bar_latest > 0:
    macd_state = "多头(DIF>0且MACD柱放大)"
elif dif_latest < 0 and bar_latest < 0:
    macd_state = "空头(DIF<0且MACD柱收缩)"
elif dif_latest > dea_latest:
    macd_state = "DIF金叉DEA，转强"
else:
    macd_state = "DIF死叉DEA，转弱"

# 3. 位置判断
current_pos = closes[-1]
pos_vs_ma = "MA5上方" if closes[-1] > ma5 else "MA5下方"
pos_vs_ma20 = "MA20上方" if closes[-1] > ma20 else "MA20下方"

print(f"  1. 均线趋势: {trend}")
print(f"  2. 均线位置: {pos_vs_ma} / {pos_vs_ma20}")
print(f"  3. MACD状态: {macd_state}")
print(f"  4. 当前位置: {current_pos:.2f} (MA5:{ma5:.2f}, MA20:{ma20:.2f}, MA60:{ma60:.2f})")

if strokes:
    last_stroke = strokes[-1]
    print(f"  5. 最新笔: {last_stroke['start_day']}~{last_stroke['end_day']} {'↓下笔' if last_stroke['type']=='bottom' else '↑上笔'} {last_stroke['start_p']:.2f}→{last_stroke['end_p']:.2f}")

print()
