import re

with open('tgb_find.html', 'r', encoding='utf-8') as f:
    html = f.read()

print('Length:', len(html))
print('Contains 爱在冰川:', '爱在冰川' in html)
print('Contains 冰川:', '冰川' in html)

# Find any blog/user links
blog_links = re.findall(r'href="(/blog/\d+[^"]*)"', html)
u_links = re.findall(r'href="(/u/\d+)"', html)
print(f'Blog links: {len(set(blog_links))}')
print(f'User links: {len(set(u_links))}')

# Find user names from links
user_blocks = re.findall(r'href="/u/(\d+)"[^>]*>([^<]+)<', html)
print(f'User name links: {len(user_blocks)}')
for uid, name in user_blocks[:20]:
    print(f'  u/{uid}: {name}')

# Find similar accounts - search results usually shown as list of bloggers
# Try to find any text mentioning the keyword
if '冰川' in html:
    idx = html.find('冰川')
    print(f'\nContext around 冰川: {html[max(0,idx-200):idx+300]}')

# Check for "no result" type messages
no_result_patterns = ['没有找到', '没有相关', '不存在', '未找到', '0 条', '0条', '找不到']
for p in no_result_patterns:
    if p in html:
        idx = html.find(p)
        print(f'\n[{p}]: {html[max(0,idx-50):idx+200]}')

# Look for blogger card structures
print('\n--- Looking for blogger cards ---')
cards = re.findall(r'class="[^"]*blogger[^"]*"', html)
print(f'Blogger classes: {len(cards)}')
cards2 = re.findall(r'class="[^"]*user-card[^"]*"', html)
print(f'User-card classes: {len(cards2)}')