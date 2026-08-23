import requests
from bs4 import BeautifulSoup
import csv
import os
from urllib.parse import urljoin
from datetime import datetime, timedelta
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# 定义网站的基准URL
BASE_URL = "https://www.jiuyangongshe.com"

def scrape_article_details(article_url):
    """
    使用Selenium抓取文章详情页的完整内容，包括动态加载部分。
    """
    # 确保你的系统中已安装ChromeDriver并设置了环境变量。
    # 否则，你需要指定驱动程序的路径
    # s = Service('/path/to/your/chromedriver')
    # driver = webdriver.Chrome(service=s)
    
    driver = webdriver.Chrome()

    try:
        print(f"    -> 正在用浏览器打开文章: {article_url}")
        driver.get(article_url)
        
        # 增加等待时间至30秒
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'text-box'))
            )
        except TimeoutException:
            print("       等待超时，文章内容可能未加载。")
            return "抓取超时"
        
        # 获取渲染后的完整页面HTML
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        
        # 找到并提取文章内容
        content_tag = soup.find('div', class_='text-box')
        
        if content_tag:
            return content_tag.get_text(strip=True)
        else:
            print("       文章内容标签未找到。")
            return "文章内容未找到"
            
    except Exception as e:
        print(f"       抓取文章详情页时发生错误：{e}")
        return "抓取失败"
        
    finally:
        driver.quit() # 无论成功或失败，确保关闭浏览器进程

def scrape_and_save_to_csv(url, filename='jiuyangongshe_full_data.csv'):
    """
    抓取搜索结果页，遍历每个链接，并抓取文章详情页的完整内容，最后保存到CSV。
    """
    # 定义请求头以模拟浏览器
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    # 初始化用于存储数据的列表和分页计数器
    scraped_data = []
    page = 1
    stop_scraping = False
    
    # 定义时间条件
    now = datetime.now()
    if now.hour < 12:
        # 如果是中午12点前，停止条件是昨天下午3点之前
        stop_time = (now - timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
    elif now.hour >= 15:
        # 如果是下午3点后，停止条件是今天0点之前
        stop_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # 其他时间段（中午12点到下午3点之间），没有特殊时间限制，正常抓取所有文章
        stop_time = None

    # 主循环，用于翻页抓取
    while not stop_scraping:
        current_url = f"{url}&page={page}"
        print(f"\n---> 正在抓取第 {page} 页: {current_url}")

        try:
            response = requests.get(current_url, headers=headers, timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"请求网页时发生错误：{e}")
            break # 停止循环

        soup = BeautifulSoup(response.text, 'html.parser')
        list_items = soup.find_all('li', {'data-v-c2edcf14': ''})
        
        # 如果当前页没有数据，说明已经到最后一页，停止循环
        if not list_items:
            print("已到达最后一页，没有更多文章。")
            break

        for i, item in enumerate(list_items):
            try:
                print(f"--- 正在处理第 {i + 1} 个项目（第 {page} 页）---")
                
                # 从搜索结果页提取基本数据和日期
                author = item.find('div', class_='fs16-bold').get_text(strip=True)
                date_str = item.find('div', class_='fs13-ash').get_text(strip=True)
                title = item.find('div', class_='book-title').get_text(strip=True)

                # 将日期字符串转换为datetime对象进行比较
                article_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')

                # 检查是否达到停止条件
                if stop_time and article_date < stop_time:
                    print(f"已达到时间限制，文章发布时间为 {article_date}，停止抓取。")
                    stop_scraping = True
                    break # 跳出当前页面循环
                
                # 找到文章的相对链接
                article_link_tag = item.find('div', class_='html-text').find('a')
                if not article_link_tag:
                    continue

                relative_url = article_link_tag.get('href')
                if not relative_url:
                    continue
                    
                full_article_url = urljoin(BASE_URL, relative_url)
                
                # 调用Selenium函数抓取文章详情
                full_content = scrape_article_details(full_article_url)
                
                # 将数据组织成字典
                data_dict = {
                    '作者': author,
                    '日期': date_str,
                    '标题': title,
                    '文章链接': full_article_url,
                    '完整内容': full_content
                }
                scraped_data.append(data_dict)
                
            except Exception as e:
                print(f"处理第 {i + 1} 个项目时发生意外错误：{e}。跳过此项目。")
                continue
        
        # 如果在内部循环中设置了停止标志，则退出外层循环
        if stop_scraping:
            break
            
        page += 1 # 准备抓取下一页
    
    # 循环结束后，将所有数据写入CSV文件
    if scraped_data:
        fieldnames = ['作者', '日期', '标题', '文章链接', '完整内容']
        
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(scraped_data)
            print(f"\n数据已成功保存到文件：{os.path.abspath(filename)}")
        except Exception as e:
            print(f"写入CSV文件时发生错误：{e}")
    else:
        print("\n没有可保存的数据。")

if __name__ == "__main__":
    target_url = "https://www.jiuyangongshe.com/search/new?k=%E5%A4%8D%E7%9B%98"
    scrape_and_save_to_csv(target_url)
