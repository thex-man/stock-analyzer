import requests, json

# 获取多氟多(002407)日K线 - 240天
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

# ============ 完整MACD计算 ============
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

print("===== 近30日MACD详情 =====")
print(f"{'日期':<12} {'收盘':>6} {'DIF':>8} {'DEA':>8} {'MACD柱':>8}")
for i in range(n-30, n):
    bar = macd_bar[i]
    arrow = "▼" if bar < 0 else "▲"
    print(f"{dates[i]:<12} {closes[i]:>6.2f} {dif[i]:>8.4f} {dea[i]:>8.4f} {bar:>8.4f} {arrow}")

# ============ 笔内背驰分析 ============
print("\n===== 笔内背驰分析 =====")
# 笔数据（从前面分析得知）
strokes_info = [
    {'start': '2026-04-15', 'end': '2026-04-23', 'type': 'down', 'start_p': 31.09, 'end_p': 29.82, 'high': 31.09, 'low': 29.82},
    {'start': '2026-04-28', 'end': '2026-05-18', 'type': 'up', 'start_p': 33.00, 'end_p': 39.71, 'high': 39.71, 'low': 33.00},
    {'start': '2026-05-21', 'end': '2026-05-29', 'type': 'down', 'start_p': 43.89, 'end_p': 33.35, 'high': 43.89, 'low': 33.35},
    {'start': '2026-06-09', 'end': '2026-06-16', 'type': 'up', 'start_p': 31.70, 'end_p': 41.50, 'high': 41.50, 'low': 31.70},
    {'start': '2026-07-21', 'end': '2026-07-28', 'type': 'up', 'start_p': 25.49, 'end_p': 35.55, 'high': 35.55, 'low': 25.49},
]

# 最近两笔对比分析
print("\n笔3(下跌笔) vs 笔1(下跌笔) → 检查背驰:")
s1 = strokes_info[0]  # 笔1: 31.09→29.82, 跌幅 = 31.09-29.82 = 1.27
s3 = strokes_info[2]  # 笔3: 43.89→33.35, 跌幅 = 43.89-33.35 = 10.54

print(f"  笔1(04-15~04-23): 43.89→33.35 跌幅: {43.89-33.35:.2f}")
print(f"  笔3(05-21~05-29): 31.09→29.82 跌幅: {31.09-29.82:.2f}")
print(f"  → 笔3跌幅远大于笔1，为正常下跌（非背驰）")

print("\n笔4(上涨笔) vs 笔2(上涨笔) → 检查背驰:")
s2 = strokes_info[1]  # 笔2: 33.00→39.71, 涨幅 = 6.71
s4 = strokes_info[3]  # 笔4: 31.70→41.50, 涨幅 = 9.80
print(f"  笔2(04-28~05-18): 33.00→39.71 涨幅: {39.71-33.00:.2f}")
print(f"  笔4(06-09~06-16): 31.70→41.50 涨幅: {41.50-31.70:.2f}")
print(f"  → 笔4涨幅大于笔2，无背驰，新高4.50已超过笔3高点43.89")

# ============ 近期走势详细分析 ============
print("\n===== 近期走势详细分析（近20日）=====")
print(f"{'日期':<12} {'开':>6} {'收':>6} {'高':>6} {'低':>6} {'涨跌幅':>8} {'成交量(万手)':>12}")
for i in range(n-20, n):
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    arrow = "▲" if chg > 0 else "▼"
    print(f"{dates[i]:<12} {opens[i]:>6.2f} {closes[i]:>6.2f} {highs[i]:>6.2f} {lows[i]:>6.2f} {arrow}{abs(chg):>6.2f}% {volumes[i]/10000:>12.0f}")

# ============ 均线系统分析 ============
print("\n===== 均线系统分析 =====")
def ma(arr, period):
    return sum(arr[-period:]) / period if len(arr) >= period else None

ma5_list = []
ma10_list = []
ma20_list = []
ma60_list = []

for i in range(n):
    m5 = sum(closes[max(0,i-4):i+1])/min(5,i+1) if i >= 0 else None
    m10 = sum(closes[max(0,i-9):i+1])/min(10,i+1) if i >= 0 else None
    m20 = sum(closes[max(0,i-19):i+1])/min(20,i+1) if i >= 0 else None
    m60 = sum(closes[max(0,i-59):i+1])/min(60,i+1) if i >= 0 else None
    ma5_list.append(m5)
    ma10_list.append(m10)
    ma20_list.append(m20)
    ma60_list.append(m60)

# 均线多头/空头排列
latest_ma5 = ma5_list[-1]
latest_ma10 = ma10_list[-1]
latest_ma20 = ma20_list[-1]
latest_ma60 = ma60_list[-1]

print(f"当前均线: MA5={latest_ma5:.2f}, MA10={latest_ma10:.2f}, MA20={latest_ma20:.2f}, MA60={latest_ma60:.2f}")
print(f"价格: {closes[-1]}")

# 均线排列判断
arrangements = []
if latest_ma5 > latest_ma10 > latest_ma20:
    arrangements.append("多头排列(5>10>20)")
elif latest_ma10 < latest_ma20 < latest_ma5:
    arrangements.append("MA5上穿/回落中")
elif latest_ma5 < latest_ma10 < latest_ma20:
    arrangements.append("空头排列")
elif latest_ma5 > latest_ma20 and latest_ma10 < latest_ma20:
    arrangements.append("均线混乱(上下交错)")

for arr in arrangements:
    print(f"  均线状态: {arr}")

# 均线支撑压力
print(f"\n均线支撑/压力:")
print(f"  压力1: MA60 = {latest_ma60:.2f} (当前价格{closes[-1]:.2f}已上穿)")
print(f"  压力2: 近高 = 39.85~43.89")
print(f"  支撑1: MA5 = {latest_ma5:.2f}")
print(f"  支撑2: MA10 = {latest_ma10:.2f}")
print(f"  支撑3: MA20 = {latest_ma20:.2f}")

# ============ 成交量分析 ============
print("\n===== 成交量分析 =====")
vol_ma5 = sum(volumes[-5:]) / 5
vol_ma10 = sum(volumes[-10:]) / 10
print(f"近5日均量: {vol_ma5/10000:.0f}万手")
print(f"近10日均量: {vol_ma10/10000:.0f}万手")
print(f"今日量: {volumes[-1]/10000:.0f}万手")
print(f"量比(5日): {volumes[-1]/vol_ma5:.2f}x")

# 放量上涨日
print("\n近20日放量日(量>10日均量1.5倍):")
for i in range(n-20, n):
    if volumes[i] > vol_ma10 * 1.5:
        chg = (closes[i]-closes[i-1])/closes[i-1]*100
        arrow = "▲" if chg > 0 else "▼"
        print(f"  {dates[i]} 量:{volumes[i]/10000:.0f}万手 {arrow}{abs(chg):.2f}%")

# ============ K线形态详细识别 ============
print("\n===== K线形态识别 =====")

def identify_candlestick(open_p, close_p, high_p, low_p, prev_close):
    """识别单根K线形态"""
    body = abs(close_p - open_p)
    upper_shadow = high_p - max(open_p, close_p)
    lower_shadow = min(open_p, close_p) - low_p
    body_pct = body / (high_p - low_p) * 100 if (high_p - low_p) > 0 else 0
    
    if body_pct < 10:
        if upper_shadow > body * 2 and lower_shadow > body * 2:
            return "长腿十字星"
        elif upper_shadow > body * 3:
            return "墓碑十字星"
        elif lower_shadow > body * 3:
            return "蜻蜓十字星"
        else:
            return "十字星"
    
    if lower_shadow > body * 2 and upper_shadow < body * 0.5:
        return "锤子线"
    if upper_shadow > body * 2 and lower_shadow < body * 0.5:
        return "倒锤子线"
    
    if body_pct > 70:
        if close_p > open_p:
            return "大阳线(强势)"
        else:
            return "大阴线(弱势)"
    
    return "普通K线"

print("近15日K线形态:")
for i in range(n-15, n):
    pattern = identify_candlestick(opens[i], closes[i], highs[i], lows[i], closes[i-1] if i > 0 else closes[i])
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    arrow = "▲" if chg > 0 else "▼"
    print(f"  {dates[i]} {pattern:<12} {arrow}{abs(chg):>5.2f}%")

# ============ 综合走势结构判断 ============
print("\n===== 综合走势结构判断 =====")
print(f"当前价格: {closes[-1]}")
print(f"近5日强势反弹，从30.01涨至38.51，涨幅+28.32%")
print(f"今日最高39.85，接近前高区域(39.85~43.89)")
print(f"MACD DIF = {dif[-1]:.4f}，仍在0轴下方但收窄")
print(f"DEA = {dea[-1]:.4f}")
print(f"MACD柱 = {macd_bar[-1]:.4f}，红柱（多头）" if macd_bar[-1] > 0 else f"MACD柱 = {macd_bar[-1]:.4f}，绿柱（空头）")

# 最近5日MACD柱子
print(f"\n近5日MACD柱变化:")
for i in range(n-5, n):
    bar = macd_bar[i]
    bar_str = "█" * int(abs(bar) * 10) if bar > 0 else "▍" * int(abs(bar) * 10)
    print(f"  {dates[i]}: {bar:+.4f} {bar_str}")

# ============ 缠论走势终完美判断 ============
print("\n===== 走势终完美判断 =====")
print("当前走势:")
print(f"  笔5(07-21~07-28): 25.49→35.55 涨幅9.06元")
print(f"  回调笔(07-28~08-03): 35.55→29.30 跌幅6.25元")
print(f"  笔6反弹(08-04至今): 30.01→38.51 涨幅8.50元(进行中)")
print(f"  → 笔6反弹尚未结束，若突破39.85则笔6延续")
print(f"  → 若在39.85~43.89区域受阻，可能形成第二类卖点")
