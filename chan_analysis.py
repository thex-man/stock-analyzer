import requests, json, math

# 获取多氟多(002407)日K线
url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
params = {'symbol': 'sz002407', 'scale': '240', 'ma': '5', 'datalen': '120'}
r = requests.get(url, params=params, timeout=10)
data = r.json()

dates = [d['day'] for d in data]
closes = [float(d['close']) for d in data]
opens = [float(d['open']) for d in data]
highs = [float(d['high']) for d in data]
lows = [float(d['low']) for d in data]
volumes = [int(d['volume']) for d in data]

n = len(data)
latest_close = closes[-1]
latest_date = dates[-1]

# 计算均线
def ma(arr, n):
    return sum(arr[-n:]) / n

ma5 = ma(closes, 5)
ma10 = ma(closes, 10)
ma20 = ma(closes, 20)
ma60 = ma(closes, 60) if len(closes) >= 60 else None

# 计算涨跌幅
change = (closes[-1] - closes[-2]) / closes[-2] * 100 if len(closes) >= 2 else 0
change5 = (closes[-1] - closes[-6]) / closes[-6] * 100 if len(closes) >= 6 else 0
change20 = (closes[-1] - closes[-21]) / closes[-21] * 100 if len(closes) >= 21 else 0

# 计算成交量均线
vol_ma5 = sum(volumes[-5:]) / 5

print(f"股票: 多氟多 (sz002407)")
print(f"最新价: {latest_close}  涨跌: {change:+.2f}%")
print(f"MA5: {ma5:.2f}  MA10: {ma10:.2f}  MA20: {ma20:.2f}")
if ma60:
    print(f"MA60: {ma60:.2f}")
print(f"近5日涨幅: {change5:+.2f}%  近20日涨幅: {change20:+.2f}%")
print(f"最新成交量: {volumes[-1]/10000:.0f}万手  量比(5日均量): {volumes[-1]/vol_ma5:.2f}")
print()
print("近10日K线数据:")
for i in range(-10, 0):
    idx = i
    print(f"  {dates[idx]} 开:{opens[idx]:.2f} 收:{closes[idx]:.2f} 高:{highs[idx]:.2f} 低:{lows[idx]:.2f} 量:{volumes[idx]/10000:.0f}万手")

# ===== 缠论分型分析 =====
print("\n===== 缠论分析 =====")

# K线包含关系处理
def process_contain(klines):
    """处理K线包含关系，返回处理后的K线列表"""
    processed = []
    for d, o, c, h, l, v in zip(dates, opens, closes, highs, lows, volumes):
        processed.append({'day': d, 'open': o, 'close': c, 'high': h, 'low': l, 'volume': v})
    
    i = 0
    result = []
    while i < len(processed):
        if i > 0 and i < len(processed) - 1:
            prev = processed[i-1]
            curr = processed[i]
            next_k = processed[i+1]
            
            # 判断包含关系：当前K线高低点在前一K线范围内
            if prev['low'] <= curr['low'] <= prev['high'] and prev['low'] <= curr['high'] <= prev['high']:
                # 向上处理：合并
                new_high = max(prev['high'], curr['high'])
                new_low = max(prev['low'], curr['low'])
                # 取前一根的开或收作为新的开
                new_open = prev['open']
                new_close = curr['close']
                result[-1] = {'day': prev['day'], 'open': new_open, 'close': new_close, 'high': new_high, 'low': new_low, 'volume': prev['volume'] + curr['volume']}
                i += 1
                continue
            elif curr['low'] <= prev['low'] <= curr['high'] and curr['low'] <= prev['high'] <= curr['high']:
                # 向下处理：合并
                new_high = min(prev['high'], curr['high'])
                new_low = min(prev['low'], curr['low'])
                new_open = curr['open']
                new_close = prev['close']
                result[-1] = {'day': result[-1]['day'], 'open': new_open, 'close': new_close, 'high': new_high, 'low': new_low, 'volume': result[-1]['volume'] + curr['volume']}
                i += 1
                continue
        
        # 无包含关系，直接保留
        result.append(processed[i])
        i += 1
    
    return result

# 简化处理：直接用原K线找分型
# 分型：顶分型(第二根最高，最低也是最高) 底分型(第二根最低，最高也是最低)
def find_fenxing(klines):
    """找出所有分型"""
    tops = []
    bottoms = []
    for i in range(1, len(klines)-1):
        prev = klines[i-1]
        curr = klines[i]
        next_k = klines[i+1]
        
        # 顶分型：当前K线高点最高，低点也最高
        if curr['high'] > prev['high'] and curr['high'] > next_k['high'] and curr['low'] > prev['low'] and curr['low'] > next_k['low']:
            tops.append(i)
        # 底分型：当前K线低点最低，高点也最低
        elif curr['low'] < prev['low'] and curr['low'] < next_k['low'] and curr['high'] < prev['high'] and curr['high'] < next_k['high']:
            bottoms.append(i)
    
    return tops, bottoms

klines = [{'day': d, 'open': o, 'close': c, 'high': h, 'low': l, 'volume': v} 
          for d, o, c, h, l, v in zip(dates, opens, closes, highs, lows, volumes)]

tops, bottoms = find_fenxing(klines)

print(f"近120日共找到 {len(tops)} 个顶分型, {len(bottoms)} 个底分型")
print()
print("最近5个顶分型:")
for idx in tops[-5:]:
    print(f"  {dates[idx]} 高:{highs[idx]:.2f} 低:{lows[idx]:.2f}")
print()
print("最近5个底分型:")
for idx in bottoms[-5:]:
    print(f"  {dates[idx]} 高:{highs[idx]:.2f} 低:{lows[idx]:.2f}")

# ===== 笔分析 =====
# 相邻的顶分型和底分型之间构成一笔
# 上升笔: 底分型 -> 顶分型
# 下降笔: 顶分型 -> 底分型
# 至少需要5根不共用的K线

def find_strokes(klines, tops, bottoms):
    """划分笔"""
    strokes = []
    all_fenxing = sorted([(t, 'top') for t in tops] + [(b, 'bottom') for b in bottoms], key=lambda x: x[0])
    
    if len(all_fenxing) < 2:
        return strokes
    
    i = 0
    while i < len(all_fenxing) - 1:
        f1, t1 = all_fenxing[i]
        f2, t2 = all_fenxing[i+1]
        
        # 顶和底之间至少5根K线
        if abs(f2 - f1) >= 5:
            stroke_type = 'up' if t1 == 'bottom' and t2 == 'top' else 'down' if t1 == 'top' and t2 == 'bottom' else None
            if stroke_type:
                strokes.append({
                    'start_idx': f1, 'end_idx': f2,
                    'start_type': t1, 'end_type': t2,
                    'start_date': dates[f1], 'end_date': dates[f2],
                    'start_price': klines[f1]['low'] if t1 == 'bottom' else klines[f1]['high'],
                    'end_price': klines[f2]['high'] if t2 == 'top' else klines[f2]['low'],
                    'type': stroke_type
                })
        i += 1
    
    return strokes

strokes = find_strokes(klines, tops, bottoms)
print(f"\n===== 笔划分 =====")
print(f"近120日共划分 {len(strokes)} 笔")
print()
print("最近10笔:")
for s in strokes[-10:]:
    direction = "↑上涨" if s['type'] == 'up' else "↓下跌"
    print(f"  {s['start_date']} → {s['end_date']} {direction} {s['start_price']:.2f}→{s['end_price']:.2f}")

# ===== 中枢分析 =====
# 至少连续三笔有重叠区间
def find_zhongshu(strokes):
    """寻找中枢 - 三笔重叠"""
    if len(strokes) < 3:
        return []
    
    zhongsus = []
    i = 0
    while i <= len(strokes) - 3:
        s1, s2, s3 = strokes[i], strokes[i+1], strokes[i+2]
        
        # 三笔必须是同向的
        if s1['type'] != s2['type'] or s2['type'] != s3['type']:
            i += 1
            continue
        
        # 取三笔的高低点重叠区间
        if s1['type'] == 'up':
            highs_range = [s1['end_price'], s2['end_price'], s3['end_price']]
            lows_range = [s1['start_price'], s2['start_price'], s3['start_price']]
            overlap_high = min(highs_range)
            overlap_low = max(lows_range)
        else:
            highs_range = [s1['start_price'], s2['start_price'], s3['start_price']]
            lows_range = [s1['end_price'], s2['end_price'], s3['end_price']]
            overlap_high = min(highs_range)
            overlap_low = max(lows_range)
        
        if overlap_low < overlap_high:  # 有重叠
            zhongsus.append({
                'start_idx': s1['start_idx'],
                'end_idx': s3['end_idx'],
                'start_date': s1['start_date'],
                'end_date': s3['end_date'],
                'low': overlap_low,
                'high': overlap_high,
                'direction': s1['type']
            })
            i += 1
        else:
            i += 1
    
    return zhongsus

zhongsus = find_zhongshu(strokes)
print(f"\n===== 中枢分析 =====")
print(f"找到 {len(zhongsus)} 个中枢")
for z in zhongsus:
    direction = "上涨" if z['direction'] == 'up' else "下跌"
    print(f"  {z['start_date']} → {z['end_date']} [{z['low']:.2f}, {z['high']:.2f}] ({direction})")

# ===== MACD 简化计算 =====
print(f"\n===== MACD 辅助判断 =====")
ema12 = closes[0]
ema26 = closes[0]
k = 2/13
j = 2/27

for c in closes:
    ema12 = c * k + ema12 * (1-k)
    ema26 = c * j + ema26 * (1-j)

dif = ema12 - ema26
dea = dif * 0.8  # 简化

print(f" DIF(12,26): {dif:.4f}")
print(f" DEA: {dea:.4f}")
print(f" MACD柱: {(dif-dea)*2:.4f}")

# 近5日MACD柱子
macd_bars = []
for i in range(-5, 0):
    c = closes[i]
    e12 = c * k + (closes[i-1] * k / (1-k) if i > 0 else closes[0]) * (1-k)
    # 简化处理
    macd_bars.append(closes[i] - closes[i-5] if i >= 5 else 0)

print(f"\n近期趋势判断:")
if ma5 > ma20:
    print(f"  均线下: MA5({ma5:.2f}) > MA20({ma20:.2f}) → 多头排列")
else:
    print(f"  均线下: MA5({ma5:.2f}) < MA20({ma20:.2f}) → 空头排列")

if dif > 0:
    print(f"  MACD: DIF({dif:.2f}) > 0 → 多头区间")
else:
    print(f"  MACD: DIF({dif:.2f}) < 0 → 空头区间")
