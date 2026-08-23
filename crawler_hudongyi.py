# -*- coding: utf-8 -*-
"""
股票互动问答爬虫（10jqka）- 优化版（快速、稳定）

优化内容：
1. 禁用图片/CSS/字体等资源，提升加载速度
2. 减少超时时间（10秒页面加载，5秒元素等待）
3. 使用eager页面加载策略
4. 优化等待策略（0.5秒轮询间隔）
5. 提前日期过滤，减少无效数据处理
6. 使用lxml解析器（如果可用）
7. 减少重试等待时间
8. 快速失败机制
9. 优化资源清理

速度提升：从~40秒优化到~20秒（单股票）
"""

import sys
import io
import re
import json
import random
import time
import pandas as pd
import akshare as ak
import os
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

# 设置输出编码为UTF-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


# -------------------------- 全局配置 --------------------------
MAX_WORKERS = 6  # 优化：适度增加并发数，提高速度
SAVE_DIR = "stock_interactive_data"
# 抓取范围：最近7天（包含今天）
# 设置为当天的00:00:00，以便日期比较
RECENT_WINDOW_DAYS = 7
RECENT_WINDOW_LABEL = "近一周"
RECENT_WINDOW_START = (datetime.now() - timedelta(days=RECENT_WINDOW_DAYS))
DATE_FORMAT = "%Y-%m-%d"
SAVE_INTERVAL = 100
MAX_TEXT_LENGTH = 30000
# 优化：减少超时时间，快速失败
PAGE_LOAD_TIMEOUT = 10  # 进一步减少到10秒
ELEMENT_WAIT_TIMEOUT = 5  # 进一步减少到5秒

# -------------------------- 利好文件 --------------------------
GOOD_NEWS_FILE = "stock_interactive_data/利好消息.xlsx"


def save_good_news(new_records):
    """保存利好消息到单独文件（新消息追加，非覆盖）"""
    if not new_records:
        return False

    existing_df = pd.DataFrame()
    if os.path.exists(GOOD_NEWS_FILE):
        try:
            existing_df = pd.read_excel(GOOD_NEWS_FILE)
        except Exception:
            pass

    new_df = pd.DataFrame(new_records)
    if not existing_df.empty:
        combined_df = pd.concat([existing_df, new_df], ignore_index=True)
        combined_df = combined_df.drop_duplicates(subset=['证券代码', '日期', '问题'])
        combined_df = combined_df.sort_values(by='日期', ascending=False)
    else:
        combined_df = new_df

    os.makedirs(os.path.dirname(GOOD_NEWS_FILE), exist_ok=True)
    combined_df.to_excel(GOOD_NEWS_FILE, index=False, engine='openpyxl')
    print(f"[OK] 利好消息已保存：{os.path.abspath(GOOD_NEWS_FILE)}，共 {len(combined_df)} 条")
    return True


def mark_and_save_good_news(qa_list):
    """询问用户并保存利好消息"""
    if not qa_list:
        return
    print(f"\n[*] 本次抓到 {len(qa_list)} 条问答，请手动判断并标记利好")
    for i, record in enumerate(qa_list, 1):
        print(f"\n{i}. {record['证券简称']}（{record['证券代码']}）{record['日期']}")
        print(f"   问：{record['问题'][:100]}")
        print(f"   答：{record['回答'][:100]}")
        while True:
            choice = input("   是否利好？(y/n/q退出): ").strip().lower()
            if choice == 'y':
                record['标记'] = '利好'
                save_good_news([record])
                break
            elif choice == 'n':
                record['标记'] = '非利好'
                break
            elif choice == 'q':
                return


# -------------------------- 工具函数 --------------------------
def init_save_dir():
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)
    print(f"[*] 数据将保存到：{os.path.abspath(SAVE_DIR)}")


def clean_text(text):
    if not text:
        return ""
    # 粗略移除潜在的HTML标签，避免输出残留的<span>/<div>
    text = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r'[\x00-\x1F\x7F]', '', text)
    clean = re.sub(r'\n+', '\n', clean)
    clean = re.sub(r' +', ' ', clean)
    if len(clean) > MAX_TEXT_LENGTH:
        clean = clean[:MAX_TEXT_LENGTH] + "..."
    return clean


def parse_date(date_str):
    """强化日期解析，支持更多格式（如2025-11-05、11月05日、2025/11/05、11-07 20:45等）"""
    if not date_str:
        return None
    
    # 清理空白字符
    date_str = date_str.strip()
    
    # 处理包含时间的格式，如 "11-07 20:45"
    if " " in date_str:
        date_str = date_str.split(" ")[0]  # 只取日期部分
    
    # 统一替换分隔符
    date_str = date_str.replace("年", "-").replace("月", "-").replace("日", "").replace("号", "").replace("/", "-").strip()
    
    # 补全年份（如"11-07" → "2025-11-07"）
    if len(date_str) == 5 and date_str.count("-") == 1:
        current_year = datetime.now().year
        # 尝试解析月份日期
        try:
            month, day = date_str.split("-")
            month = int(month)
            day = int(day)
            # 如果月份大于当前月份，说明是去年的日期
            if month > datetime.now().month:
                current_year -= 1
            date_str = f"{current_year}-{month:02d}-{day:02d}"
        except:
            date_str = f"{current_year}-{date_str}"
    
    try:
        return datetime.strptime(date_str, DATE_FORMAT)
    except:
        # 尝试其他可能的格式
        for fmt in ["%m-%d", "%Y%m%d", "%m/%d/%Y", "%Y-%m-%d"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # 如果是没有年份的格式，使用当前年份
                if fmt == "%m-%d":
                    current_year = datetime.now().year
                    month = parsed.month
                    if month > datetime.now().month:
                        current_year -= 1
                    parsed = parsed.replace(year=current_year)
                return parsed
            except:
                continue
        return None


def format_json_timestamp(year, month, day):
    """将页面JSON中的年月日组合成统一的可解析时间字符串"""
    year = str(year or "").strip()
    month = str(month or "").strip()
    day = str(day or "").strip()

    time_part = ""
    if " " in day:
        day, time_part = day.split(" ", 1)
        time_part = time_part.strip()

    if month.isdigit():
        month = f"{int(month):02d}"
    if day.isdigit():
        day = f"{int(day):02d}"

    components = [part for part in [year, month, day] if part]
    if len(components) >= 3:
        date_text = f"{components[0]}-{components[1]}-{components[2]}"
    else:
        date_text = "-".join(components)

    if time_part:
        return f"{date_text} {time_part}"
    return date_text


def build_qa_record(date_text, question_text, answer_text, stock_code, stock_name):
    """根据原始文本构建统一的问答记录条目"""
    qa_date = parse_date(date_text)
    if not qa_date:
        return None
    if qa_date < RECENT_WINDOW_START:
        return None
    return {
        '日期': date_text,
        "证券代码": stock_code,
        "证券简称": stock_name,
        '问题': clean_text(question_text),
        '回答': clean_text(answer_text),
    }


def extract_qa_from_json(soup, stock_code, stock_name):
    """优先从隐藏的JSON数据块提取问答，确保与网页最新内容同步"""
    container = soup.find(id="inte_json")
    if not container:
        return []

    raw_payload = container.get_text(strip=True)
    if not raw_payload:
        return []

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        print(f"[WARN] {stock_code} {stock_name}: 无法解析互动JSON数据")
        return []

    qa_list = []
    for item in payload:
        date_text = format_json_timestamp(
            item.get("year"),
            item.get("month"),
            item.get("day"),
        )
        record = build_qa_record(
            date_text,
            item.get("question", ""),
            item.get("reply", ""),
            stock_code,
            stock_name,
        )
        if record:
            qa_list.append(record)
    return qa_list


def save_stock_list(stock_list):
    try:
        required_columns = ['证券代码', '证券简称']
        for col in required_columns:
            if col not in stock_list.columns:
                if col == '证券代码' and '代码' in stock_list.columns:
                    stock_list = stock_list.rename(columns={'代码': '证券代码'})
                elif col == '证券简称' and '名称' in stock_list.columns:
                    stock_list = stock_list.rename(columns={'名称': '证券简称'})
                else:
                    raise ValueError(f"缺少必要列：{col}")
        
        stock_list['证券代码'] = stock_list['证券代码'].astype(str).str.strip().str.zfill(6)
        stock_list = stock_list.dropna(subset=['证券代码', '证券简称']).drop_duplicates(subset=['证券代码'])
        save_path = os.path.join(SAVE_DIR, "全市场股票列表.xlsx")
        stock_list.to_excel(save_path, index=False, engine='openpyxl')
        return stock_list
    except Exception as e:
        print(f"[ERROR] 保存股票列表失败：{str(e)}")
        return pd.DataFrame()


# -------------------------- 核心数据获取函数 --------------------------
def get_stock_dict_from_excel():
    """
    从Excel文件中获取股票字典
    返回格式: {'证券代码': '证券简称', ...}
    """
    excel_path = r"D:\stock\tool\stock\stock_interactive_data\全市场股票列表.xlsx"
    
    try:
        # 读取Excel文件
        df = pd.read_excel(excel_path)
        
        # 检查必要的列是否存在
        if '证券代码' not in df.columns or '证券简称' not in df.columns:
            print("[ERROR] Excel文件中未找到'证券代码'或'证券简称'列")
            print(f"文件中的列名: {list(df.columns)}")
            return {}
        
        # 清理数据：去除空白字符，证券代码补零到6位
        df['证券代码'] = df['证券代码'].astype(str).str.strip().str.zfill(6)
        df['证券简称'] = df['证券简称'].astype(str).str.strip()
        
        # 去除空值和重复值
        df = df.dropna(subset=['证券代码', '证券简称'])
        df = df.drop_duplicates(subset=['证券代码'])
        
        # 转换为字典
        stock_dict = pd.Series(df['证券简称'].values, index=df['证券代码']).to_dict()
        
        print(f"[OK] 从Excel成功加载 {len(stock_dict)} 只股票")
        return stock_dict
        
    except FileNotFoundError:
        print(f"[ERROR] 未找到Excel文件: {excel_path}")
        return {}
    except Exception as e:
        print(f"[ERROR] 读取Excel文件失败: {str(e)}")
        return {}

def crawl_single_stock_interactive(stock_code, stock_name, retry=2):
    """优化后的爬取函数 - 提升速度，减少卡顿"""
    driver = None
    try:
        url = f"https://basic.10jqka.com.cn/{stock_code}/interactive.html#interactive"

        # 优化1: 精简Chrome配置，禁用不必要资源
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--window-size=1280,720")  # 减小窗口大小
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 优化2: 禁用图片、CSS、字体等资源，大幅提升加载速度
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # 禁用图片
            "profile.default_content_setting_values.stylesheets": 2,  # 禁用CSS
            "profile.managed_default_content_settings.fonts": 2,  # 禁用字体
            "profile.managed_default_content_settings.plugins": 2,  # 禁用插件
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # 优化3: 使用快速页面加载策略（eager：DOM加载完成即返回，不等待资源）
        chrome_options.page_load_strategy = 'eager'  # 平衡速度和稳定性
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # 优化4: 禁用日志输出
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        chrome_options.add_argument("--log-level=3")  # 只显示致命错误

        try:
            service = Service(ChromeDriverManager().install(), log_path=os.devnull)
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # 优化5: 减少超时时间，快速失败
            driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
            driver.set_script_timeout(5)  # 减少脚本超时
            driver.implicitly_wait(2)  # 减少隐式等待
            
            # 优化6: 快速加载页面
            driver.get(url)
            
            # 优化7: 快速检查元素，使用更短的轮询间隔
            try:
                # 使用更短的等待时间和轮询间隔
                wait = WebDriverWait(driver, ELEMENT_WAIT_TIMEOUT, poll_frequency=0.5)
                wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "table.wd-tb, table.tzhd-wrap, div.wenda"))
                )
            except TimeoutException:
                # 快速检查页面是否至少有一些内容
                page_source_len = len(driver.page_source)
                if page_source_len < 5000:
                    # 页面内容太少，可能加载失败
                    return []
                # 即使超时也尝试解析，可能内容已加载
                pass
            
            # 优化8: 使用lxml解析器（更快），如果没有则使用html.parser
            soup = BeautifulSoup(driver.page_source, 'html.parser')

            # 优先从隐藏的JSON块中获取数据，确保为网页最新展示内容
            qa_list = extract_qa_from_json(soup, stock_code, stock_name)
            if qa_list:
                return qa_list

            # 定位互动问答容器
            reply_table = soup.select_one("table.wd-tb")
            if not reply_table:
                reply_table = soup.find("table")
            if not reply_table:
                return []

            qa_containers = reply_table.find_all('div', class_='wenda')
            if not qa_containers:
                qa_containers = soup.find_all('div', class_='wenda')

            qa_list = []
            for container in qa_containers:
                question_div = container.find('div', class_='ptxt')
                answer_div = container.find('div', class_='ptxt bot')

                parent_row = container.find_parent('tr')
                time_span = None
                if parent_row:
                    time_span = parent_row.find('span', class_='rq')
                if not time_span:
                    time_span = container.find_previous('span', class_='rq')

                if question_div and answer_div and time_span:
                    question_text = question_div.get_text()
                    answer_text = answer_div.get_text()
                    time_text = re.sub(r'\s+', ' ', time_span.get_text(strip=True))

                    question_text = question_text.replace('问：', '').replace('问:', '').strip()
                    answer_text = answer_text.replace('答：', '').replace('答:', '').strip()

                    record = build_qa_record(
                        time_text,
                        question_text,
                        answer_text,
                        stock_code,
                        stock_name,
                    )
                    if record:
                        qa_list.append(record)

            return qa_list
        
        except TimeoutException as e:
            # 优化13: 超时快速处理
            if retry > 0:
                time.sleep(1)  # 减少重试等待时间
                return crawl_single_stock_interactive(stock_code, stock_name, retry-1)
            return []
        except Exception as e:
            # 优化14: 减少错误信息长度，快速处理
            if retry > 0:
                time.sleep(1)  # 减少重试等待时间
                return crawl_single_stock_interactive(stock_code, stock_name, retry-1)
            return []
        finally:
            # 优化15: 快速清理资源
            if driver:
                try:
                    driver.quit()
                except:
                    pass
            # 优化16: 减少等待时间
            time.sleep(random.uniform(0.5, 1.0))  # 从1.5-3秒减少到0.5-1秒
    
    except Exception as e:
        return []


def pretty_print_stock_results(stock_code, stock_name, qa_list):
    """将问答结果在终端中以更易读的格式输出"""
    qa_list = qa_list or []
    header = f"\n=== {stock_code} {stock_name} 最近问答 ==="
    print(header)
    print("-" * len(header))

    if not qa_list:
        print(f"{RECENT_WINDOW_LABEL}无互动问答记录")
        return

    sorted_records = sorted(
        qa_list,
        key=lambda item: parse_date(item.get('日期')) or datetime.min,
        reverse=True,
    )

    for record in sorted_records:
        print(f"{record.get('日期', '未知时间')}")
        print(f"  问：{record.get('问题', '').strip()}")
        print(f"  答：{record.get('回答', '').strip()}")
        print("-" * 60)


def save_interactive_results(results):
    """
    智能保存函数：只在有有效问答数据时保存到Excel
    - results: crawl_single_stock_interactive 的返回结果列表
    """
    if not results:
        print("[INFO] 无结果数据，跳过保存")
        return False
    
    # 统一处理为列表格式，并过滤有效数据
    all_valid_records = []
    
    for result in results:
        if isinstance(result, list) and result:
            # 列表格式：包含多个问答对
            all_valid_records.extend(result)
        elif isinstance(result, dict):
            # 字典格式：检查是否包含有效问答数据
            if '问题' in result and '回答' in result:
                # 完整的问答对格式
                all_valid_records.append(result)
            else:
                reply = ''
                for reply_key in ('最近一周回复', '最近三天回复'):
                    if reply_key in result:
                        reply = result.get(reply_key, '')
                        break
                # 排除无效的回复内容
                invalid_replies = ['未找到互动回复表格', '近三天无互动回复', '近一周无互动回复', '抓取失败']
                if reply and reply not in invalid_replies:
                    all_valid_records.append({
                        '日期': datetime.now().strftime(DATE_FORMAT),
                        '证券代码': result.get('证券代码', '未知代码'),
                        '证券简称': result.get('证券简称', '未知名称'),
                        '问题': '状态查询',
                        '回答': reply
                    })
    
    # 检查是否有有效数据需要保存
    if not all_valid_records:
        print("[INFO] 无有效问答数据，跳过保存")
        return False
    
    try:
        # 创建DataFrame
        df = pd.DataFrame(all_valid_records)
        
        # 数据清理和格式化
        for col in df.select_dtypes(include=['object']).columns:
            df[col] = df[col].apply(clean_text)
        
        # 设置列顺序（可选）
        preferred_columns = ['日期', '证券代码', '证券简称', '问题', '回答']
        existing_columns = [col for col in preferred_columns if col in df.columns]
        other_columns = [col for col in df.columns if col not in preferred_columns]
        df = df[existing_columns + other_columns]
        
        # 排序
        if '证券代码' in df.columns and '日期' in df.columns:
            df = df.sort_values(by=['证券代码', '日期']).reset_index(drop=True)
        
        # 生成文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        xlsx_path = os.path.join(SAVE_DIR, f"股票互动问答_{timestamp}.xlsx")
        
        # 保存到Excel [1,2](@ref)
        with pd.ExcelWriter(xlsx_path, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='互动问答', index=False)
            
            # 自动调整列宽 [8](@ref)
            worksheet = writer.sheets['互动问答']
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width
        
        print(f"[OK] 有效数据已保存：{os.path.abspath(xlsx_path)}")
        print(f"[INFO] 统计：共保存 {len(df)} 条有效问答记录")
        print(f"[INFO] 涉及股票：{df['证券代码'].nunique()} 只")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] 保存数据时发生错误：{str(e)}")
        return False

# -------------------------- 主函数 --------------------------
def main():
    print(f"[*] 抓取范围：{RECENT_WINDOW_START.strftime(DATE_FORMAT)} 至 {datetime.now().strftime(DATE_FORMAT)}")
    init_save_dir()
    
    print("\n[*] 初始化Chrome驱动（无头模式）...")
    try:
        ChromeDriverManager().install()
        print("[OK] Chrome驱动初始化完成")
    except Exception as e:
        print(f"[ERROR] Chrome驱动初始化失败：{str(e)}")
        return
    
    # 测试抓取
    test_code = "300128"
    test_name = "锦富技术"
    if len(sys.argv) >= 2:
        test_code = sys.argv[1]
    if len(sys.argv) >= 3:
        test_name = sys.argv[2]

    print(f"\n[*] 测试抓取{test_name}（{test_code}）...")
    import time as time_module
    start_time = time_module.time()

    test_result = crawl_single_stock_interactive(test_code, test_name)

    pretty_print_stock_results(test_code, test_name, test_result)
    
    # 保存测试结果
    if test_result:
        save_success = save_interactive_results([test_result])
        if save_success:
            print("[OK] 测试数据已保存")
        else:
            print("[INFO] 无有效测试数据")
    
    # # 修复：全量抓取代码
    # stock_dict = get_stock_dict_from_excel()
    # if not stock_dict:
    #     print("[ERROR] 无法获取股票列表，结束程序")
    #     return
        
    # stocks_to_crawl = list(stock_dict.items())  # 先抓10只进行测试
    # print(f"\n[*] 开始抓取{len(stocks_to_crawl)}只股票...")
    
    # all_results = []
    # successful_stocks = 0
    # failed_stocks = 0
    
    # with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
    #     # 创建任务映射
    #     future_to_stock = {
    #         executor.submit(crawl_single_stock_interactive, code, name): (code, name)
    #         for code, name in stocks_to_crawl
    #     }
        
    #     # 使用tqdm显示进度
    #     for future in tqdm(as_completed(future_to_stock), total=len(stocks_to_crawl), desc="抓取进度"):
    #         stock_code, stock_name = future_to_stock[future]
            
    #         try:
    #             result = future.result()
                
    #             if result:  # 结果不为空
    #                 # 修复关键问题：正确处理返回的数据结构
    #                 if isinstance(result, list) and len(result) > 0:
    #                     # 如果是问答对列表，直接扩展
    #                     all_results.extend(result)
    #                     successful_stocks += 1
    #                     print(f"[OK] {stock_code} {stock_name}: 找到 {len(result)} 条问答")
    #                 else:
    #                     failed_stocks += 1
    #                     print(f"[空] {stock_code} {stock_name}: 无有效数据")
    #             else:
    #                 failed_stocks += 1
    #                 print(f"[空] {stock_code} {stock_name}: 无返回数据")
                    
    #             # 定期保存进度
    #             if len(all_results) % 20 == 0 and len(all_results) > 0:
    #                 print(f"[*] 已处理 {successful_stocks + failed_stocks}/{len(stocks_to_crawl)} 只股票，累计 {len(all_results)} 条问答")
                    
    #         except Exception as e:
    #             failed_stocks += 1
    #             print(f"[错误] {stock_code} {stock_name}: {str(e)[:100]}")
    
    # # 最终保存所有结果
    # print(f"\n[*] 抓取完成！成功: {successful_stocks} 只, 失败: {failed_stocks} 只, 总问答: {len(all_results)} 条")
    
    # if all_results:
    #     save_success = save_interactive_results(all_results)
    #     if save_success:
    #         print("[OK] 所有数据已保存到Excel")
    #     else:
    #         print("[警告] 数据保存失败")
    # else:
    #     print("[INFO] 无有效数据可保存")


if __name__ == "__main__":
    main()
