import re

with open('tgb_search.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find blog links with text
blog_matches = re.findall(r'href="(/blog/\d+[^"]*)"[^>]*>([^<]+)</a>', html)
print(f'Blog links: {len(blog_matches)}')
for url, text in blog_matches[:20]:
    print(f'  {text.strip()[:40]} -> {url}')

# Check for placeholder messages
markers = ['没有', '未找到', 'no-result', '暂无', '没有找到', '0条', '空']
for m in markers:
    if m in html:
        idx = html.find(m)
        print(f'\n[{m}] context: ...{html[max(0,idx-50):idx+200]}...')

# Try to find any user-related content
user_hrefs = re.findall(r'href="(/u/\d+)"', html)
print(f'\nUser hrefs: {len(user_hrefs)}: {list(set(user_hrefs))[:10]}')