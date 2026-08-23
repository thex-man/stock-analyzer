import requests

# 获取上证指数日K线 - 扩大范围
url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
params = {'symbol': 'sh000001', 'scale': '240', 'ma': '5', 'datalen': '500'}
r = requests.get(url, params=params, timeout=10)
data = r.json()

dates = [d['day'] for d in data]
closes = [float(d['close']) for d in data]
opens = [float(d['open']) for d in data]
highs = [float(d['high']) for d in data]
lows = [float(d['low']) for d in data]

n = len(data)

def ma(arr, period):
    if len(arr) < period:
        return None
    return sum(arr[-period:]) / period

# 找近250日最高点和最低点
recent = 250
r_dates = dates[-recent:]
r_closes = closes[-recent:]
r_highs = highs[-recent:]
r_lows = lows[-recent:]

max_high = max(r_highs)
max_high_idx = r_highs.index(max_high)
min_low = min(r_lows)
min_low_idx = r_lows.index(min_low)

print(f"{'='*60}")
print(f"  上证指数 大级别ABC浪分析 (近{recent}日)")
print(f"{'='*60}")

print(f"\n近250日区间: {r_dates[0]} ~ {r_dates[-1]}")
print(f"最高点: {r_dates[max_high_idx]} = {max_high:.2f}")
print(f"最低点: {r_dates[min_low_idx]} = {min_low:.2f}")

# 缠论分型 - 大级别
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

# 大级别分型 - 用所有数据，但筛选近200日的
all_tops = get_fenxing(klines, 'top')
all_bottoms = get_fenxing(klines, 'bottom')

# 合并过滤异向
all_fx = [(t['idx'], t) for t in all_tops] + [(b['idx'], b) for b in all_bottoms]
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

# 找近250日内的分型
recent_fx = [(idx, fx) for idx, fx in filtered if idx >= n - recent]

print(f"\n--- 近250日关键分型点 ---\n")
for idx, fx in recent_fx:
    label = "▲顶" if fx['type'] == 'top' else "▼底"
    print(f"  {fx['day']}  {label}  高:{fx['high']:.2f}  低:{fx['low']:.2f}")

# ============ 大ABC浪划分 ============
print(f"\n{'='*60}")
print(f"  大级别ABC浪划分")
print(f"{'='*60}")

# 找到近250日最低点后的第一波上涨
# 最低点: min_low_idx (相对于recent)
abs_min_low_idx = n - recent + min_low_idx

print(f"\n最低点: {r_dates[min_low_idx]} = {min_low:.2f} (索引: {abs_min_low_idx})")
print(f"最高点: {r_dates[max_high_idx]} = {max_high:.2f} (索引: {n-recent+max_high_idx})")

# 从最低点到最高点是一段上涨
# 从最高点到现在是一个下跌修正

# 计算波浪
# 5浪上涨: 最低点 → 最高点
# A浪下跌: 最高点 → ?

# 取区间
a_start_idx = n - recent + max_high_idx  # 最高点索引
a_end_idx = n - 1  # 今日（数据最新日）
a_start_val = max_high
a_end_val = closes[-1]

a_len = a_start_val - a_end_val

print(f"\n--- A浪 ---")
print(f"  起点: {dates[a_start_idx]}  {a_start_val:.2f}")
print(f"  终点: {dates[a_end_idx]}  {a_end_val:.2f}")
print(f"  跌幅: {a_len:.2f}点 ({(a_len/a_start_val)*100:.2f}%)")

# 计算B浪反弹目标
b_382 = a_end_val + a_len * 0.382
b_500 = a_end_val + a_len * 0.500
b_618 = a_end_val + a_len * 0.618
b_786 = a_end_val + a_len * 0.786

print(f"\n--- B浪反弹目标位 ---")
print(f"  0.382: {b_382:.2f}")
print(f"  0.500: {b_500:.2f}")
print(f"  0.618: {b_618:.2f}")
print(f"  0.786: {b_786:.2f}")

# C浪目标
c_100 = a_end_val - a_len       # 等长
c_123 = a_end_val - a_len * 1.23
c_1618 = a_end_val - a_len * 1.618

print(f"\n--- C浪目标位 ---")
print(f"  C = A 等长: {c_100:.2f}")
print(f"  C = 1.23A: {c_123:.2f}")
print(f"  C = 1.618A: {c_1618:.2f}")

# ============ 均线系统 ============
ma5 = ma(closes, 5)
ma10 = ma(closes, 10)
ma20 = ma(closes, 20)
ma60 = ma(closes, 60)
ma120 = ma(closes, 120) if n >= 120 else None
ma250 = ma(closes, 250) if n >= 250 else None

print(f"\n--- 均线系统 ---")
print(f"  MA5:  {ma5:.2f}")
print(f"  MA10: {ma10:.2f}")
print(f"  MA20: {ma20:.2f}")
print(f"  MA60: {ma60:.2f}")
if ma120: print(f"  MA120: {ma120:.2f}")
if ma250: print(f"  MA250: {ma250:.2f}")

# 判断均线多空
if ma5 > ma10 > ma20:
    ma_trend = "多头排列"
elif ma5 < ma10 < ma20:
    ma_trend = "空头排列"
else:
    ma_trend = "混乱排列"
print(f"  趋势: {ma_trend}")

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

print(f"\n--- MACD ---")
print(f"  DIF: {dif[-1]:.4f}")
print(f"  DEA: {dea[-1]:.4f}")
print(f"  MACD柱: {macd_bar[-1]:.4f}")
print(f"  近10日MACD柱: ", end="")
for i in range(n-10, n):
    bar = macd_bar[i]
    sign = "+" if bar > 0 else ""
    print(f"{sign}{bar:.1f} ", end="")
print()

# ============ 近30日K线 ============
print(f"\n--- 近30日K线 ---\n")
print(f"  {'日期':<12} {'开':>7} {'收':>7} {'高':>7} {'低':>7} {'涨跌':>7}")
for i in range(n-30, n):
    chg = (closes[i]-closes[i-1])/closes[i-1]*100 if i > 0 else 0
    arrow = "▲" if chg > 0 else "▼"
    print(f"  {dates[i]:<12} {opens[i]:>7.2f} {closes[i]:>7.2f} {highs[i]:>7.2f} {lows[i]:>7.2f} {arrow}{abs(chg):>5.2f}%")

# ============ 大浪型判断 ============
print(f"\n{'='*60}")
print(f"  综合判断 - 大级别浪型")
print(f"{'='*60}")

# 从数据看：最低点到现在是一轮上涨+下跌
# 近250日最高点4258在5/14，然后跌到8/19的3894
# 这是A浪下跌，幅度: 4258 - 3894 = 364点

print(f"""
从大级别看:

  最高点: {dates[a_start_idx]}  {a_start_val:.2f}
  最低点: {r_dates[min_low_idx]}  {min_low:.2f}
  
  → 这是一个大级别的上涨波段后的A浪下跌

  A浪幅度: {a_len:.2f}点 ({(a_len/a_start_val)*100:.2f}%)
  A浪走了多少了？

  判断:
  · 从4258高点跌到3894，跌幅{a_len:.0f}点，属于较大级别的A浪
  · 当前位置{closes[-1]:.2f} vs MA60({ma60:.0f}): {"在MA60上方" if closes[-1] > ma60 else "在MA60下方"}
  · MACD DIF={dif[-1]:.2f}: {"零轴上方，多头" if dif[-1] > 0 else "零轴下方，空头"}

  关键路径:
  1. A浪可能还没走完（若A=364点全貌，C目标约3530~3444）
  2. 若已走完，则当前位置在B反弹中
     - B反弹目标: {b_382:.0f} ~ {b_618:.0f}
  3. C浪目标: {c_100:.0f} ~ {c_1618:.0f}

  均线配合:
  · MA5({ma5:.0f}) > MA10({ma10:.0f}) > MA20({ma20:.0f}): {ma_trend}
  · 当前位置{closes[-1]:.2f} 在MA60({ma60:.0f}){"上" if closes[-1]>ma60 else "下"}
""")

# ============ 更长期的结构 ============
print(f"\n{'='*60}")
print(f"  更长期结构 (全部历史数据)")
print(f"{'='*60}")

# 从全部500日数据找结构
all_max_high = max(highs)
all_max_high_idx = highs.index(all_max_high)
all_min_low = min(lows)
all_min_low_idx = lows.index(all_min_low)

print(f"\n数据范围: {dates[0]} ~ {dates[-1]} (共{n}根K线)")
print(f"历史最高: {dates[all_max_high_idx]} = {all_max_high:.2f}")
print(f"历史最低: {dates[all_min_low_idx]} = {all_min_low:.2f}")

# 近500日范围
recent500_fx = [(idx, fx) for idx, fx in filtered if idx >= n - 500]
print(f"\n近500日关键分型点:")
for idx, fx in recent500_fx[-15:]:
    label = "▲顶" if fx['type'] == 'top' else "▼底"
    print(f"  {fx['day']}  {label}  高:{fx['high']:.2f}  低:{fx['low']:.2f}")
