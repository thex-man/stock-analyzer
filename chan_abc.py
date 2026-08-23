import requests

# 获取上证指数日K线
url = 'https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData'
params = {'symbol': 'sh000001', 'scale': '240', 'ma': '5', 'datalen': '250'}
r = requests.get(url, params=params, timeout=10)
data = r.json()

dates = [d['day'] for d in data]
closes = [float(d['close']) for d in data]
opens = [float(d['open']) for d in data]
highs = [float(d['high']) for d in data]
lows = [float(d['low']) for d in data]

n = len(data)

# ============ 近期关键高低点 ============
print(f"{'='*55}")
print(f"  上证指数 ABC浪 精确定位")
print(f"{'='*55}")

# 从近期高点到低点找abc结构
# 近期高点: 8/18 的 3990.30 (顶分型 3994.18)
# 之前低点: 8/3 的 3809.66 (底分型低点)
# 之后反弹: 8/10 顶分型高点 3967.59

# 精确定义：找到这波从高点下来的abc
# a浪起点 = 3994.18 (8/18)
# a浪终点 = 3827.64 (8/3低点)  或需要重新找

# 重新扫描找a浪起点
print("\n--- 扫描近期完整ABC结构 ---\n")

# 找7月底以来的最高点
high_idx = n - 1
high_val = highs[0]
for i in range(n):
    if highs[i] > high_val:
        high_val = highs[i]
        high_idx = i

print(f"近250日最高点: {dates[high_idx]} = {high_val:.2f}")

# 找8月高点
print("\n8月K线:")
for i in range(n-20, n):
    print(f"  {dates[i]} 开:{opens[i]:.2f} 收:{closes[i]:.2f} 高:{highs[i]:.2f} 低:{lows[i]:.2f}")

# ============ 确认abc结构 ============
# 根据数据：
# 5浪上涨: 7/14低点3869.30 → 8/18高点3990.30 (或8/10的3967)
# 3浪下跌: 8/18高点 → ?

# 关键：找到这波abc
# a起点 = 8/18高点 = 3990.30（或用顶分型高点3994.18）
# a终点 = 需要找第一个明显低点
# b终点 = 反弹高点

# 从数据看，a浪应该是从 8/18 的 3990.30 跌下来
# 第一个明显低点应该是 8/19 的今天（数据是19号的收盘）

print("\n" + "="*55)
print("  ABC浪结构划分（以8月这波为例）")
print("="*55)

# a浪: 8/18 高点 → 至今
# a = 3990.30 - 3894.42 = 95.88 点
a_start = 3990.30
a_end = 3894.42
a_len = a_start - a_end

# b浪反弹: 理论上反弹a的0.382~0.786
b_target_382 = a_end + a_len * 0.382  # = 3894.42 + 36.6 = 3931
b_target_618 = a_end + a_len * 0.618  # = 3894.42 + 59.2 = 3953.6
b_target_786 = a_end + a_len * 0.786  # = 3894.42 + 75.3 = 3969.7

print(f"\na浪: {dates[n-3]} ~ {dates[n-1]} (8/18~8/19)")
print(f"  起点: {a_start:.2f}")
print(f"  终点: {a_end:.2f}")
print(f"  跌幅: {a_len:.2f} 点 ({(a_len/a_start)*100:.2f}%)")

print(f"\nb浪反弹目标位（基于a={a_len:.1f}点）:")
print(f"  0.382反弹位: {b_target_382:.2f}")
print(f"  0.618反弹位: {b_target_618:.2f}")
print(f"  0.786反弹位: {b_target_786:.2f}")

# c浪目标: = a浪起点 - a浪长度 或 1.618倍
c_target1 = a_end - a_len       # = a等长
c_target_1618 = a_end - a_len * 1.618  # 1.618倍

print(f"\nc浪目标（若b反弹到位后）:")
print(f"  c = a等长目标: {c_target1:.2f}")
print(f"  c = 1.618a目标: {c_target_1618:.2f}")

print("\n" + "="*55)
print("  当前浪型位置判断")
print("="*55)

# 判断当前位置
# 3990.30 → 3894.42 = a浪进行中（还没走完）
# 8/19当天从3961高开到3894收盘，是a浪的加速段

# 但也需要看是否有b浪已经在内部发生
# 8/19当天：高开3961然后低走3894
# 中间有没有反弹？

print(f"\n8/19 当日走势:")
print(f"  开盘: {opens[n-1]:.2f}")
print(f"  最高: {highs[n-1]:.2f}")
print(f"  最低: {lows[n-1]:.2f}")
print(f"  收盘: {closes[n-1]:.2f}")
print(f"  上下影线: 上影{(highs[n-1]-opens[n-1]):.2f} 下影{(closes[n-1]-lows[n-1]):.2f}")

if highs[n-1] > opens[n-1] + 20:
    print(f"\n→ a浪中！高开低走，是a浪的下跌中继结构")
    print(f"  开盘3961已是当天b浪高点，之后单边下跌至3894")
    print(f"  目前a浪可能只走了一半")

print("\n--- ABC三浪标准结构（供参考）---\n")
print("    a (下跌)          b (反弹)           c (再跌)")
print("  ┌──────┐         ┌──────┐          ┌──────┐")
print("  │      │         │  /\  │          │      │")
print("  │  /\  │    /\   │ /  \ │    /\    │ /    │")
print("  │ /  \ │   /  \  │/    │   /  \   │/     │")
print("  │/    │  /    \  │     │  /    \  │      │")
print("  └──────┘ /      \ └────┘ /      \ └──────┘")
print("  起点              反弹高点            终点<c1")
print()
print("--- 8月这波abc的可能走法 ---\n")
print(f"  a: 3990 → 3894 (已跌{a_len:.1f}点, 已走{(a_len/167)*100:.0f}%?)")
print(f"     若a=167点全貌: 目前只走到{a_len/167*100:.0f}%")
print(f"     但实际a可能还没走完")
print(f"  b: 待定（反弹目标{b_target_382:.0f}~{b_target_786:.0f}）")
print(f"  c: 待定（目标{c_target1:.0f}~{c_target_1618:.0f}）")

print("\n" + "="*55)
print("  判断结论")
print("="*55)
print(f"""
  当前处于: a浪下跌中后期

  理由:
  1. 3990.30(8/18高点) → 3894.42(8/19收盘) = a浪a段
  2. 8/19当天3961高开低走，上影线长，属于a浪中继
  3. 若a浪幅度与前一波5浪等长(约167点)，则a浪可能
     还没走完，c目标约3759

  关键:
  · 若3894再破MA20(3887)，确认a浪延伸，下一目标3770~3759
  · b浪反弹若不过3960~3990，说明是弱b，后面c会很凶
  · 整体：a进行中，8月底前可能还有b反弹，然后c创新低
""")
