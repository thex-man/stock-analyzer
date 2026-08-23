# -*- coding: utf-8 -*-
"""
enrich_stock_data.py
-------------------
为 concept_data 目录下的 JSON 文件补充以下字段：

1. market_data        - 当日行情（价格/涨跌幅/成交量/成交额/换手率）
                       来源: akshare stock_zh_a_spot (Sina) 【注意：不含PE/PB/市值，Eastmoney接口被封】
2. financial_data     - 财务摘要（净利润/营收/EPS/ROE等）  来源: stock_financial_abstract_ths
3. shareholder_top10  - 前十大股东                        来源: stock_main_stock_holder
4. shareholder_change  - 近期股东增减持                    来源: stock_shareholder_change_ths
5. dividend_history   - 分红历史                          来源: stock_dividend_cninfo
6. important_dates    - 重要日期（财报/分红/解禁）         来源: 各接口汇总

使用方式:
    单股测试: python enrich_stock_data.py 000001
    全量更新: python enrich_stock_data.py --all
    指定日期(YYYY-MM-DD): python enrich_stock_data.py --date 2025-06-17
"""

import json
import os
import sys
import time
import warnings
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, date, timedelta
from pathlib import Path

import re
import akshare as ak
import pandas as pd

warnings.filterwarnings('ignore')

# ===================== 配置 =====================
CONCEPT_DATA_DIR = Path(r"D:\stock\tool\stock\concept_data")
OUTPUT_DIR = Path(r"D:\stock\tool\stock\concept_data_enriched")
CACHE_FILE = OUTPUT_DIR / "market_data_cache.json"  # 缓存全量行情，避免每次重抓

OUTPUT_DIR.mkdir(exist_ok=True)

# ===================== 行情数据（Sina，全量一次抓） =====================
def fetch_market_data_all():
    """从 Sina 抓全市场行情，返回 dict: {纯代码: {最新价, 涨跌幅, 成交量, 成交额, ...}}"""
    if CACHE_FILE.exists():
        cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
        cache_date = cache.get('_cache_date', '')
        today = date.today().isoformat()
        if cache_date == today and 'data' in cache:
            print(f"[行情缓存] 使用今日缓存 {today}，共 {len(cache['data'])} 只")
            return cache['data']

    print("[行情] 正在从 Sina 抓取全市场行情...")
    try:
        df = ak.stock_zh_a_spot()
        result = {}
        for _, row in df.iterrows():
            raw_code = str(row['代码'])  # 格式: sz000001 / sh600036 / bj920000
            # 去掉前缀，保留纯代码
            code = raw_code[2:].zfill(6)
            result[code] = {
                '最新价': float(row['最新价']) if pd.notna(row['最新价']) else None,
                '涨跌幅': float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                '涨跌额': float(row['涨跌额']) if pd.notna(row['涨跌额']) else None,
                '成交量': float(row['成交量']) if pd.notna(row['成交量']) else None,
                '成交额': float(row['成交额']) if pd.notna(row['成交额']) else None,
                '最高': float(row['最高']) if pd.notna(row['最高']) else None,
                '最低': float(row['最低']) if pd.notna(row['最低']) else None,
                '今开': float(row['今开']) if pd.notna(row['今开']) else None,
                '昨收': float(row['昨收']) if pd.notna(row['昨收']) else None,
                '时间戳': str(row.get('时间戳', '')),
                '_raw_code': raw_code,  # 保留原始码方便调试
            }
        cache = {'_cache_date': date.today().isoformat(), 'data': result}
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"[行情] 抓取完成，共 {len(result)} 只，缓存至 {CACHE_FILE}")
        return result
    except Exception as e:
        print(f"[行情] 抓取失败: {e}")
        if CACHE_FILE.exists():
            cache = json.loads(CACHE_FILE.read_text(encoding='utf-8'))
            if 'data' in cache:
                return cache['data']
        return {}


# ===================== 财务摘要（THS） =====================
def fetch_financial_data(stock_code: str) -> dict:
    """从同花顺抓财务摘要数据"""
    try:
        df = ak.stock_financial_abstract_ths(symbol=stock_code)
        if df is None or df.empty:
            return {}
        # 取最新一期（第一行）
        row = df.iloc[0]
        return {
            '报告期': str(row.get('报告期', '')),
            '净利润': parse_chinese_number(row.get('净利润')),
            '净利润同比增长率': parse_chinese_number(row.get('净利润同比增长率')),
            '扣非净利润': parse_chinese_number(row.get('扣非净利润')),
            '营业总收入': parse_chinese_number(row.get('营业总收入')),
            '营业总收入同比增长率': parse_chinese_number(row.get('营业总收入同比增长率')),
            '基本每股收益': parse_chinese_number(row.get('基本每股收益')),
            '每股净资产': parse_chinese_number(row.get('每股净资产')),
            '每股资本公积金': parse_chinese_number(row.get('每股资本公积金')),
            '每股未分配利润': parse_chinese_number(row.get('每股未分配利润')),
            '每股经营现金流': parse_chinese_number(row.get('每股经营现金流')),
            '销售净利率': parse_chinese_number(row.get('销售净利率')),
            '净资产收益率': parse_chinese_number(row.get('净资产收益率')),
            '净资产收益率-摊薄': parse_chinese_number(row.get('净资产收益率-摊薄')),
            '资产负债率': parse_chinese_number(row.get('资产负债率')),
            '存货周转率': parse_chinese_number(row.get('存货周转率')),
            '应收账款周转天数': parse_chinese_number(row.get('应收账款周转天数')),
        }
    except Exception as e:
        return {}


# ===================== 前十大股东 =====================
def fetch_shareholder_top10(stock_code: str) -> list:
    """获取前十大股东"""
    try:
        df = ak.stock_main_stock_holder(stock=stock_code)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                '股东名称': str(row.get('股东名称', '')),
                '持股数量': float(row['持股数量']) if pd.notna(row.get('持股数量')) else None,
                '持股比例': float(row['持股比例']) if pd.notna(row.get('持股比例')) else None,
                '股本性质': str(row.get('股本性质', '')),
                '截至日期': str(row.get('截至日期', '')),
                '公告日期': str(row.get('公告日期', '')),
            })
        return result
    except Exception as e:
        return []


# ===================== 股东增减持 =====================
def fetch_shareholder_changes(stock_code: str, days: int = 180) -> list:
    """获取近 N 天股东增减持记录"""
    try:
        df = ak.stock_shareholder_change_ths(symbol=stock_code)
        if df is None or df.empty:
            return []
        result = []
        cutoff = date.today() - timedelta(days=days)
        for _, row in df.iterrows():
            raw_date = row.get('公告日期')
            # 统一转为 date 对象
            if hasattr(raw_date, 'date'):
                ann_date = raw_date.date() if hasattr(raw_date, 'hour') else raw_date
            elif isinstance(raw_date, str):
                ann_date = datetime.fromisoformat(raw_date[:10]).date()
            else:
                continue
            if ann_date < cutoff:
                continue
            result.append({
                '公告日期': ann_date.isoformat(),
                '变动股东': str(row.get('变动股东', '')),
                '变动数量': str(row.get('变动数量', '')),
                '变动数量_数值': parse_chinese_number(row.get('变动数量')),
                '交易均价': float(row['交易均价']) if pd.notna(row.get('交易均价')) else None,
                '变动期间': str(row.get('变动期间', '')),
                '变动途径': str(row.get('变动途径', '')),
            })
        return result
    except Exception as e:
        return []


# ===================== 分红历史 =====================
def fetch_dividend_history(stock_code: str, limit: int = 10) -> list:
    """获取分红历史（最近 N 条）"""
    try:
        df = ak.stock_dividend_cninfo(symbol=stock_code)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.head(limit).iterrows():
            result.append({
                '实施方案公告日期': str(row.get('实施方案公告日期', ''))[:10],
                '分红类型': str(row.get('分红类型', '')),
                '送股比例': float(row['送股比例']) if pd.notna(row.get('送股比例')) else 0.0,
                '转增比例': float(row['转增比例']) if pd.notna(row.get('转增比例')) else 0.0,
                '派息比例': float(row['派息比例']) if pd.notna(row.get('派息比例')) else 0.0,
                '股权登记日': str(row.get('股权登记日', ''))[:10] if pd.notna(row.get('股权登记日')) else None,
                '除权日': str(row.get('除权日', ''))[:10] if pd.notna(row.get('除权日')) else None,
                '派息日': str(row.get('派息日', ''))[:10] if pd.notna(row.get('派息日')) else None,
            })
        return result
    except Exception as e:
        return []


# ===================== 重要日期汇总 =====================
def fetch_important_dates(stock_code: str) -> dict:
    """汇总所有重要日期信息"""
    div_history = fetch_dividend_history(stock_code, limit=5)
    dividend_dates = []
    for d in div_history:
        for field in ['股权登记日', '除权日', '派息日', '实施方案公告日期']:
            val = d.get(field)
            if val and val not in ['', 'None', 'NaT']:
                dividend_dates.append({'日期': val, '类型': f'分红-{field}', '内容': f"派息比例:{d.get('派息比例', 0)}"})

    return {
        '分红': dividend_dates,
        '数据更新时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


# ===================== 速率限制 =====================
TRATE = 0.5  # 每次请求间隔秒数（并发下适当缩小）

# ===================== 工具函数 =====================
def parse_chinese_number(val) -> float:
    """解析 '6053.45万', '1.66亿', '11.82%' 等为 float"""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if s in ('', 'None', 'False', 'True'):
        return None
    # 百分比：去掉 %
    is_percent = '%' in s
    s = s.replace('%', '')
    # 亿/万
    multiplier = 1.0
    if '亿' in s:
        multiplier = 1e8
        s = s.replace('亿', '')
    elif '万' in s:
        multiplier = 1e4
        s = s.replace('万', '')
    try:
        result = float(s) * multiplier
        if is_percent:
            result = result / 100.0
        return result
    except (ValueError, TypeError):
        return None

def enrich_stock(stock_code: str, market_data_all: dict) -> dict:
    """对单只股票进行数据丰富化"""
    print(f"  处理 {stock_code}...", end='', flush=True)

    enriched = {}

    # 1. 行情
    md = market_data_all.get(stock_code, {})
    enriched['market_data'] = md

    # 2. 财务摘要
    time.sleep(TRATE)
    enriched['financial_data'] = fetch_financial_data(stock_code)

    # 3. 前十大股东
    time.sleep(TRATE)
    enriched['shareholder_top10'] = fetch_shareholder_top10(stock_code)

    # 4. 股东增减持（近180天）
    time.sleep(TRATE)
    enriched['shareholder_changes'] = fetch_shareholder_changes(stock_code, days=180)

    # 5. 分红历史
    time.sleep(TRATE)
    enriched['dividend_history'] = fetch_dividend_history(stock_code, limit=10)

    # 6. 重要日期
    enriched['important_dates'] = fetch_important_dates(stock_code)

    print(" 完成")
    return enriched


def update_json(stock_code: str, enriched: dict):
    """将丰富化数据合并写入原 JSON 文件（新增字段）"""
    json_path = CONCEPT_DATA_DIR / f"{stock_code}_concepts.json"
    if not json_path.exists():
        return

    try:
        content = json.loads(json_path.read_text(encoding='utf-8'))
        content['enrichment'] = enriched
        content['enrich_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # 尝试补充 market_data 到顶层
        if 'market_data' in enriched and enriched['market_data']:
            md = enriched['market_data']
            content['current_price'] = md.get('最新价')
            content['price_change_pct'] = md.get('涨跌幅')
            content['volume'] = md.get('成交量')
            content['turnover'] = md.get('成交额')
        json_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    except Exception as e:
        print(f"  写入失败 {stock_code}: {e}")


# ===================== 批量处理 =====================
def process_all(target_date: str = None, max_workers: int = 16):
    """批量更新所有 JSON 文件，16线程并发"""
    market_data_all = fetch_market_data_all()

    files = sorted(CONCEPT_DATA_DIR.glob("*_concepts.json"))
    total = len(files)
    success = 0
    fail = 0
    lock = threading.Lock()

    print(f"\n开始批量丰富化，共 {total} 个文件，线程数={max_workers}")
    print("=" * 60)

    def process_one(f):
        code = f.stem.replace('_concepts', '')
        try:
            enriched = enrich_stock(code, market_data_all)
            update_json(code, enriched)
            return code, True, None
        except Exception as e:
            return code, False, str(e)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(process_one, f): f for f in files}
        for i, future in enumerate(as_completed(futures), 1):
            code, ok, err = future.result()
            with lock:
                if ok:
                    success += 1
                else:
                    fail += 1
                    print(f"  {code} 处理失败: {err}")
                if i % 100 == 0 or i == total:
                    print(f"[进度] {i}/{total}，成功 {success}，失败 {fail}")

    print("=" * 60)
    print(f"完成！成功 {success}/{total}，失败 {fail}")


# ===================== 单股测试 =====================
def test_single(stock_code: str):
    """测试单只股票"""
    market_data_all = fetch_market_data_all()
    enriched = enrich_stock(stock_code, market_data_all)
    update_json(stock_code, enriched)

    # 打印结果
    print(f"\n{'=' * 60}")
    print(f"{stock_code} 丰富化结果预览:")
    print(f"{'=' * 60}")
    md = enriched.get('market_data', {})
    print(f"行情: 最新价={md.get('最新价')}, 涨跌幅={md.get('涨跌幅')}%, 成交量={md.get('成交量')}")
    fd = enriched.get('financial_data', {})
    print(f"财务: 净利润={fd.get('净利润')}, EPS={fd.get('基本每股收益')}, ROE={fd.get('净资产收益率')}")
    sc = enriched.get('shareholder_changes', [])
    print(f"股东增减持: 近180天共 {len(sc)} 条")
    for c in sc[:3]:
        print(f"  - {c.get('公告日期')} {c.get('变动股东')}: {c.get('变动数量')}")
    dh = enriched.get('dividend_history', [])
    print(f"分红: 最近 {len(dh)} 条")
    for d in dh[:3]:
        print(f"  - {d.get('实施方案公告日期')}: 派息{d.get('派息比例')}")


# ===================== 入口 =====================
if __name__ == '__main__':
    args = sys.argv[1:]

    if not args:
        print(__doc__)
    elif args[0] == '--all':
        process_all()
    elif args[0] == '--date':
        target = args[1] if len(args) > 1 else date.today().isoformat()
        print(f"指定日期: {target} (全量模式)")
        process_all(target)
    else:
        code = args[0].zfill(6)
        test_single(code)
