"""
Wechat Public Account Article Crawler
Target: https://mp.weixin.qq.com/ via Sogou Weixin search
"""
import requests
from bs4 import BeautifulSoup
import csv
import os
import time
from datetime import datetime

# ========== CONFIG ==========
TARGET_ACCOUNT = "E_ZaiBingChuan"  # partial URL identifier, or Chinese name
MAX_PAGES = 3
OUTPUT_FILE = "wechat_aizaibingchuan.csv"
# ============================

def get_articles_via_sogou(keyword, max_pages=3):
    """
    Crawl Wechat public account articles via Sogou Weixin search.
    Sogou Weixin: https://weixin.sogou.com/
    """
    articles = []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://weixin.sogou.com/",
    }

    for page in range(max_pages):
        if page == 0:
            url = f"https://weixin.sogou.com/weixin?type=1&s_from=input&query={requests.utils.quote(keyword)}&ie=utf8&_sug_=n&_sug_type_="
        else:
            url = f"https://weixin.sogou.com/weixin?type=1&s_from=input&query={requests.utils.quote(keyword)}&ie=utf8&page={page+1}"
        
        print(f"[*] Page {page+1}: {url[:80]}")
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            print(f"    Status: {resp.status_code}, Content length: {len(resp.text)}")
            resp.encoding = 'utf-8'
            soup = BeautifulSoup(resp.text, 'html.parser')

            # Selector: news-list items on Sogou Weixin search results
            items = soup.select('ul.news-list2 li, ul.list_box li, .news-box .news-list li')
            print(f"    Found {len(items)} items")
            
            if not items:
                # Debug: print first 500 chars of page
                print(f"    [DEBUG] Page content preview: {resp.text[:500]}")
            
            for item in items:
                try:
                    # Try multiple title selectors
                    title = ''
                    for sel in ['.txt-box h3 a', '.info h3 a', 'h3 a', '.title a']:
                        t = item.select_one(sel)
                        if t:
                            title = t.get_text(strip=True)
                            link = t.get('href', '')
                            break
                    if not title:
                        continue
                    
                    # Date selector
                    date = ''
                    for sel in ['.s-p', '.time', '.date', '.s2']:
                        d = item.select_one(sel)
                        if d:
                            date = d.get_text(strip=True)
                            break
                    
                    # Account name
                    account = ''
                    for sel in ['.account', '.s2', '.account-nick']:
                        a = item.select_one(sel)
                        if a:
                            account = a.get_text(strip=True)
                            break
                    
                    articles.append({
                        'account': account or keyword,
                        'title': title,
                        'date': date,
                        'url': link,
                        'crawl_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    })
                except Exception as e:
                    print(f"    [!] Parse item error: {e}")
                    continue
            
            time.sleep(3)
            
        except Exception as e:
            print(f"    [!] Request error: {e}")
            break
    
    return articles

def get_article_content(url):
    """Get full article content from a Wechat article URL."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = 'utf-8'
        soup = BeautifulSoup(resp.text, 'html.parser')
        for selector in ['#js_content', '.rich_media_content', '#img-content']:
            tag = soup.select_one(selector)
            if tag:
                return tag.get_text(separator='\n', strip=True)[:5000]
        return "Content selector not found"
    except Exception as e:
        return f"Error: {e}"

def save_csv(data, filename):
    if not data:
        print("[!] No data to save")
        return
    fieldnames = ['account', 'title', 'date', 'url', 'crawl_time']
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"[+] Saved {len(data)} articles to {os.path.abspath(filename)}")

def main():
    print("=" * 60)
    print(f"Wechat Article Crawler - Target: {TARGET_ACCOUNT}")
    print("=" * 60)
    
    print("\n[*] Step 1: Crawling article list from Sogou Weixin...")
    articles = get_articles_via_sogou(TARGET_ACCOUNT, max_pages=MAX_PAGES)
    
    print(f"\n[+] Total articles found: {len(articles)}")
    
    if articles:
        for i, art in enumerate(articles[:10], 1):
            print(f"  {i}. [{art['date']}] {art['title']}")
        
        save_csv(articles, OUTPUT_FILE)
        
        # Optionally fetch full content for first 3 articles
        print("\n[*] Step 2: Fetching full content for first 3 articles...")
        for i, art in enumerate(articles[:3], 1):
            if art['url']:
                print(f"\n  --- Article {i} ---")
                content = get_article_content(art['url'])
                print(f"  Preview: {content[:200]}")
                art['content'] = content
    else:
        print("[!] No articles found. Sogou might require captcha or anti-bot.")
        print("[!] Try: 1) Use Selenium with real browser; 2) Use RSSHub; 3) Use browser extension")

if __name__ == "__main__":
    main()
