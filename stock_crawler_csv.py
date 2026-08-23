import time
import pandas as pd
import akshare as ak
from tqdm import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- 全局设置 ---
# 设置线程池的最大线程数，可以根据您的CPU和网络情况调整
MAX_WORKERS = 16  # 减少线程数，避免被反爬

def get_chixnext_stocks():
    """
    使用 akshare 获取所有创业板股票的代码和名称字典。
    """
    try:
        print("正在从akshare获取最新的创业板股票列表...")
        stock_list = ak.stock_info_sz_name_code()
        # 筛选出创业板股票（代码以'30'开头）
        chixnext_stocks_df = stock_list[stock_list['A股代码'].str.startswith('30')]
        # 创建一个 {代码: 名称} 格式的字典
        stock_info = pd.Series(chixnext_stocks_df['A股简称'].values, index=chixnext_stocks_df['A股代码']).to_dict()
        print(f"成功获取到 {len(stock_info)} 只创业板股票。")
        return stock_info
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return {}

def crawl_stock_concepts(stock_code, stock_name):
    """
    抓取单个股票代码的概念题材（适配版）。
    返回结果时使用股票名称。
    """
    url = f"https://basic.10jqka.com.cn/{stock_code}/concept.html"
    
    # --- 复用文件中的反爬虫Chrome选项 ---
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
        # 关键：增加等待时间，确保表格数据加载
        time.sleep(5)
        
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, 'html.parser')
            
        concepts = []
        # --- 使用你提供的核心逻辑：精准定位概念表格 ---
        concept_table = None 
        tables = soup.find_all('table')
        for table in tables:
            # 通过表头内容定位到正确的表格
            if table.find('th', string=lambda text: text and '概念名称' in text):
                concept_table = table
                break

        # --- 从已定位的表格中提取概念 ---
        if concept_table:
            # 跳过表头行 (tr[1:]), 遍历所有数据行
            for row in concept_table.find_all('tr')[1:]:
                cols = row.find_all('td')
                # 概念名称在第二列 (索引为1)
                if len(cols) >= 2:
                    concept_name = cols[1].get_text(strip=True)
                    if concept_name:
                        concepts.append(concept_name)

            if concepts:
            # 返回包含股票名称和概念的字典
                return {"name": stock_name, "concepts": ", ".join(concepts)}
        else:
            # 如果没找到，明确标记为无
            return {"name": stock_name, "concepts": "无"}

    except Exception as e:
        # 在多线程中，打印错误而不是中断程序
        # print(f"抓取 {stock_code} 时出错: {e}")
        return None
    finally:
        if driver:
            driver.quit()
        # 保留文件中的随机延迟
        time.sleep(0.5 + float(stock_code[-2:])/100)


def save_results_to_csv(results, filename):
    """
    辅助函数：将结果列表保存到指定的CSV文件。
    """
    if not results:
        print("结果列表为空，不执行保存操作。")
        return
        
    print(f"\n达到保存点，正在将 {len(results)} 条数据保存到文件: {filename}...")
    try:
        df = pd.DataFrame(results)
        # 按股票名称排序
        df = df.sort_values(by="name").reset_index(drop=True)
        # 将DataFrame保存到CSV文件，不包含索引，使用 utf-8-sig 编码以正确显示中文
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"数据已成功更新到: {filename}")
    except Exception as e:
        print(f"保存到CSV文件时出错: {e}")


def main():
    """
    主函数：调度多线程抓取并保存结果。
    """
    stock_info = get_chixnext_stocks()
    
    if not stock_info:
        print("没有可抓取的股票代码，程序退出。")
        return

    print(f"\n准备开始多线程抓取 {len(stock_info)} 只股票的概念题材...")
    print(f"使用 {MAX_WORKERS} 个线程。这可能需要一些时间，请耐心等待。")
    
    all_results = []
    output_filename = "all_chixnext_concepts.csv"  # 修改输出文件名
    save_interval = 50
    
    # 使用ThreadPoolExecutor进行多线程处理
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 创建future任务列表，同时传入代码和名称
        future_to_stock = {executor.submit(crawl_stock_concepts, code, name): name for code, name in stock_info.items()}
        
        # 使用tqdm创建进度条
        for future in tqdm(as_completed(future_to_stock), total=len(stock_info), desc="抓取进度"):
            result = future.result()
            if result:
                all_results.append(result)
                
                # 检查是否达到了保存的阈值
                if len(all_results) % save_interval == 0:
                    save_results_to_csv(all_results, output_filename)

    if not all_results:
        print("\n所有抓取任务均失败，未生成任何数据。")
        return

    print(f"\n抓取完成！成功获取了 {len(all_results)} 只股票的数据。")
    
    # --- 最终保存 ---
    print("正在进行最后的数据保存...")
    save_results_to_csv(all_results, output_filename)
    
    print(f"所有结果已最终保存到文件: {output_filename}")




if __name__ == "__main__":
    # 确保webdriver-manager在首次运行时不会因日志过长而混淆
    print("正在初始化WebDriver Manager，首次运行可能需要下载驱动...")
    try:
        # 预热一下，让它把驱动下载好
        ChromeDriverManager().install()
        print("WebDriver Manager 初始化完成。")
    except Exception as e:
        print(f"WebDriver Manager 初始化失败: {e}")
        exit()

    main()
