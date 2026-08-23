import time
import pandas as pd
import akshare as ak
import os
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 全局设置 ---
MAX_WORKERS = 8  # 线程数
# 创建保存目录
SAVE_DIR = "stock_data"
if not os.path.exists(SAVE_DIR):
    os.makedirs(SAVE_DIR)

def save_stock_list(stock_list, board_type, board_name):
    """专门用于保存股票列表到Excel的函数"""
    try:
        # 确保列名正确
        required_columns = ['证券代码', '证券简称']
        for col in required_columns:
            if col not in stock_list.columns:
                # 尝试自动修复常见的列名差异
                if col == '证券代码' and '代码' in stock_list.columns:
                    stock_list = stock_list.rename(columns={'代码': '证券代码'})
                elif col == '证券简称' and '名称' in stock_list.columns:
                    stock_list = stock_list.rename(columns={'名称': '证券简称'})
                else:
                    raise ValueError(f"股票列表缺少必要的列: {col}")
        
        # 构建保存路径
        filename = f"{board_type}_stock_list.xlsx"
        save_path = os.path.join(SAVE_DIR, filename)
        
        # 保存到Excel
        stock_list.to_excel(save_path, index=False, engine='openpyxl')
        print(f"✅ {board_name}股票列表已保存 ({len(stock_list)} 条记录):")
        print(f"   路径: {os.path.abspath(save_path)}")
        return True
    except Exception as e:
        print(f"❌ 保存{board_name}股票列表失败: {str(e)}")
        return False

def get_stocks_by_board(board_type):
    """获取各板块股票列表并保存到Excel"""
    try:
        board_name = get_board_name(board_type)
        print(f"正在从akshare获取最新的{board_name}股票列表...")
        
        # 不同板块的股票获取逻辑
        if board_type == 'chuangye':  # 创业板
            try:
                stock_list = ak.stock_info_sz_name_code().rename(columns={'A股代码': '证券代码', 'A股简称': '证券简称'})
                stock_list = stock_list[(stock_list['板块'] == '创业板') & (stock_list['证券代码'].str.startswith('3'))]
                print("stock_list:", stock_list)
            except AttributeError:
                stock_list = ak.stock_info_a_code_name()
        
        elif board_type == 'kechuang':  # 科创板
            try:
                stock_list = ak.stock_info_sh_name_code("科创板")
                print("stock_list:", stock_list)
            except AttributeError:
                try:
                    stock_list = ak.stock_info_sh_name_code("科创板")
                except AttributeError:
                    print("使用代码筛选法获取科创板股票...")
                    stock_sh = ak.stock_info_sh_name_code("科创板")
                    stock_sh = stock_sh.rename(columns={'代码': '证券代码', '名称': '证券简称'})
                    stock_list = stock_sh[stock_sh['证券代码'].str.startswith('688')]
        
        elif board_type == 'beijiao':  # 北交所
            try:
                stock_list = ak.stock_info_bj_name_code()
                print("stock_list:", stock_list)
            except AttributeError:
                print("使用代码筛选法获取北交所股票...")
                stock_sh = ak.stock_info_sh_name_code().rename(columns={'代码': '证券代码', '名称': '证券简称'})
                stock_sz = ak.stock_info_sz_name_code().rename(columns={'代码': '证券代码', '名称': '证券简称'})
                stock_list = pd.concat([stock_sh, stock_sz], ignore_index=True)
                stock_list = stock_list[stock_list['证券代码'].str.startswith('8')]
        
        elif board_type == 'main':  # 主板
            sh_main = ak.stock_info_sh_name_code().rename(columns={'代码': '证券代码', '名称': '证券简称'})
            sh_main = sh_main[~sh_main['证券代码'].str.startswith('688')]  # 排除科创板
            sz_main = ak.stock_info_sz_name_code().rename(columns={'代码': '证券代码', '名称': '证券简称'})
            sz_main = sz_main[~sz_main['证券代码'].str.startswith('30')]  # 排除创业板
            stock_list = pd.concat([sh_main, sz_main], ignore_index=True)
        
        else:
            print(f"不支持的板块类型: {board_type}")
            return {}
        
        # 数据清洗
        stock_list['证券代码'] = stock_list['证券代码'].astype(str).str.strip()
        stock_list = stock_list.dropna(subset=['证券代码', '证券简称'])
        stock_list = stock_list[stock_list['证券代码'].str.len() >= 6]
        stock_list = stock_list.drop_duplicates(subset=['证券代码'])
        
        # 保存股票列表
        save_stock_list(stock_list, board_type, board_name)
        
        # 创建股票信息字典
        stock_info = pd.Series(
            stock_list['证券简称'].values, 
            index=stock_list['证券代码']
        ).to_dict()
        
        print(f"成功获取到 {len(stock_info)} 只{board_name}股票。")
        return stock_info
        
    except Exception as e:
        print(f"获取{get_board_name(board_type)}股票列表失败: {e}")
        print("提示: 尝试更新AKShare到最新版本: pip install akshare --upgrade")
        return {}

def get_board_name(board_type):
    """获取板块的中文名称"""
    board_names = {
        'chuangye': '创业板',
        'kechuang': '科创板',
        'main': '主板',
        'beijiao': '北交所'
    }
    return board_names.get(board_type, board_type)

def crawl_stock_concepts(stock_code, stock_name):
    """抓取单个股票代码的概念题材"""
    url = f"https://basic.10jqka.com.cn/{stock_code}/concept.html"
    
    # 反爬虫设置
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    service = Service(ChromeDriverManager().install(), log_path=None)
    
    driver = None
    try:
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        driver.get(url)
        time.sleep(1)
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
            
        concepts = []
        concept_table = None 
        tables = soup.find_all('table')
        for table in tables:
            if table.find('th', string=lambda text: text and '概念名称' in text):
                concept_table = table
                break

        if concept_table:
            for row in concept_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                if len(cols) >= 2:
                    concept_name = cols[1].get_text(strip=True)
                    if concept_name:
                        concepts.append(concept_name)

            if concepts:
                return {"code": stock_code, "name": stock_name, "concepts": ", ".join(concepts)}
        return {"code": stock_code, "name": stock_name, "concepts": "无"}

    except Exception as e:
        return {"code": stock_code, "name": stock_name, "concepts": f"抓取失败: {str(e)}"}
    finally:
        if driver:
            driver.quit()
        time.sleep(0.5 + float(stock_code[-2:])/100)

def save_results_to_excel(results, board_type, board_name):
    """保存概念抓取结果"""
    if not results:
        print("结果列表为空，不执行保存操作。")
        return
        
    filename = f"{board_type}_concepts.xlsx"
    save_path = os.path.join(SAVE_DIR, filename)
    print(f"\n正在将 {len(results)} 条数据保存到文件...")
    try:
        df = pd.DataFrame(results)
        df = df.sort_values(by="code").reset_index(drop=True)
        df.to_excel(save_path, index=False, engine='openpyxl')
        print(f"✅ 概念数据已保存: {os.path.abspath(save_path)}")
    except Exception as e:
        print(f"❌ 保存概念数据失败: {e}")

def crawl_board_concepts(board_type):
    """抓取指定板块的所有股票概念"""
    stock_codes = get_stocks_by_board(board_type)
    board_name = get_board_name(board_type)
    
    if not stock_codes:
        print(f"没有可抓取的{board_name}股票代码，跳过该板块。")
        return

    print(f"\n准备开始多线程抓取 {len(stock_codes)} 只{board_name}股票的概念题材...")
    
    all_results = []
    save_interval = 50
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_stock = {executor.submit(crawl_stock_concepts, code, name): code for code, name in stock_codes.items()}
        
        for future in tqdm(as_completed(future_to_stock), total=len(stock_codes), desc=f"{board_name}抓取进度"):
            result = future.result()
            if result:
                all_results.append(result)
                
                if len(all_results) % save_interval == 0:
                    save_results_to_excel(all_results, board_type, board_name)

    if not all_results:
        print(f"\n{board_name}所有抓取任务均失败，未生成任何数据。")
        return

    print(f"\n{board_name}抓取完成！成功获取了 {len(all_results)} 只股票的数据。")
    save_results_to_excel(all_results, board_type, board_name)

def main():
    """主函数：选择要抓取的板块并调度多线程抓取"""
    print(f"数据将保存到目录: {os.path.abspath(SAVE_DIR)}")
    
    # 初始化WebDriver
    print("\n正在初始化WebDriver Manager...")
    try:
        ChromeDriverManager().install()
        print("WebDriver Manager 初始化完成。")
    except Exception as e:
        print(f"WebDriver Manager 初始化失败: {e}")
        exit()
    
    # 支持的板块列表
    boards = [
        {'code': 'main', 'name': '主板'},
        {'code': 'kechuang', 'name': '科创板'},
        {'code': 'chuangye', 'name': '创业板'},
        {'code': 'beijiao', 'name': '北交所'}
    ]
    
    # 显示板块选择菜单
    print("\n请选择要抓取的股票板块：")
    for i, board in enumerate(boards, 1):
        print(f"{i}. {board['name']}")
    print(f"{len(boards)+1}. 抓取所有板块")
    
    try:
        choice = int(input("请输入选项 (1-5): ")) - 1
        
        if choice == len(boards):  # 抓取所有板块
            for board in boards:
                print(f"\n===== 开始抓取{board['name']} =====")
                crawl_board_concepts(board['code'])
                print(f"===== {board['name']}抓取结束 =====\n")
        elif 0 <= choice < len(boards):  # 抓取单个板块
            selected_board = boards[choice]
            print(f"\n===== 开始抓取{selected_board['name']} =====")
            crawl_board_concepts(selected_board['code'])
            print(f"===== {selected_board['name']}抓取结束 =====\n")
        else:
            print("无效的选项")
    except ValueError:
        print("请输入有效的数字")


if __name__ == "__main__":
    main()
