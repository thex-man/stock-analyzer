# -*- coding: utf-8 -*-
"""
【已废弃】2026-08-27 移除

MACD 滚动 v2.0 tab 已被移除（v4 不再生成 sheet9_macd_latest.html）。
本脚本保留作为 stub，不再实际注入 tab。

如果未来重新启用 v2.0 滚动，请恢复原脚本。
"""
import sys
print('[DEPRECATED] inject_macd_tab.py is deprecated as of 2026-08-27.', file=sys.stderr)
print('[DEPRECATED] MACD v2 滚动 tab no longer injected into dashboard.', file=sys.stderr)
print('[DEPRECATED] This script is now a no-op stub.', file=sys.stderr)
sys.exit(0)


# === 以下代码保留供恢复使用 ===
# import os, re, shutil
# from datetime import datetime
# from bs4 import BeautifulSoup, NavigableString
#
# DASHBOARD = r'D:\stock\tool\stock\data\每日复盘看板.html'
# LATEST_HTML = r'D:\stock\tool\stock\reports\macd_latest.html'
# TAB_ID = 'MACD滚动截面'
# TAB_LABEL = '?? MACD滚动截面（v2.0）'
# SCOPE_CLASS = 'macd-content'
#
#
# def _today_iso():
#     return datetime.now().strftime('%Y-%m-%d %H:%M')


def scope_css(css_text, prefix):
    """
    给 CSS 每个选择器加上前缀 class，避免全局污染。
    例如 prefix='.macd-content'：
      'body { ... }'      -> '.macd-content body { ... }' （但仅在 .macd-content 内生效）
      '.kpi { ... }'      -> '.macd-content .kpi { ... }'
      'h1, h2 { ... }'    -> '.macd-content h1, .macd-content h2 { ... }'
    """
    out = []
    for block in re.split(r'(/\*.*?\*/)', css_text, flags=re.DOTALL):
        if block.startswith('/*'):
            out.append(block)
            continue
        # 拆分为 "selector { props }" 块
        i = 0
        while i < len(block):
            brace = block.find('{', i)
            if brace == -1:
                tail = block[i:].strip()
                if tail:
                    out.append(tail)
                break
            selector_text = block[i:brace].strip()
            # 找匹配的 }
            depth = 1
            j = brace + 1
            while j < len(block) and depth > 0:
                if block[j] == '{':
                    depth += 1
                elif block[j] == '}':
                    depth -= 1
                j += 1
            props = block[brace+1:j-1]
            if selector_text and props:
                # 处理每个选择器（逗号分隔）
                new_selectors = []
                for sel in selector_text.split(','):
                    sel = sel.strip()
                    if not sel:
                        continue
                    # 跳过 :root, @-rules
                    if sel.startswith('@') or sel == ':root':
                        new_selectors.append(sel)
                        continue
                    # 加上前缀
                    new_selectors.append(f'{prefix} {sel}')
                if new_selectors:
                    out.append(', '.join(new_selectors) + ' {' + props + '}')
            i = j
    return '\n'.join(out)


# 备份看板
backup = DASHBOARD + '.bak'
if not os.path.exists(backup):
    shutil.copy2(DASHBOARD, backup)
    print(f'已备份到: {backup}')
else:
    print(f'备份已存在: {backup}')

# 解析看板
with open(DASHBOARD, 'r', encoding='utf-8') as f:
    dashboard_html = f.read()

soup = BeautifulSoup(dashboard_html, 'html.parser')

# 1. 删除旧的 MACD tab 按钮（如果存在）
old_tab_btn = soup.find('button', class_='tab', onclick=lambda v: v and f"showTab('{TAB_ID}'" in v)
if old_tab_btn:
    old_tab_btn.decompose()
    print(f'已删除旧 tab 按钮')

# 2. 删除旧的 MACD panel（如果存在）
old_panel = soup.find('div', id=f'tab-{TAB_ID}')
if old_panel:
    old_panel.decompose()
    print(f'已删除旧 panel')

# 3. 解析 MACD 最新报告，提取 body 内部
with open(LATEST_HTML, 'r', encoding='utf-8') as f:
    macd_html = f.read()
macd_soup = BeautifulSoup(macd_html, 'html.parser')
macd_body = macd_soup.find('body')
if not macd_body:
    print('错误: macd_latest.html 没有 body 标签')
    raise SystemExit(1)

# 4. 创建新 tab 按钮，插入到 tabs 容器的末尾
tabs_container = soup.find('div', class_='tabs')
if not tabs_container:
    print('错误: 找不到 tabs 容器')
    raise SystemExit(1)
new_btn = soup.new_tag('button', attrs={'class': 'tab',
                                         'onclick': f"showTab('{TAB_ID}', this)"})
new_btn.string = TAB_LABEL
tabs_container.append(new_btn)
print(f'已插入新 tab 按钮')

# 4.5 把 MACD 里的 <style> scope 后合并到看板 head（保证 KPI 卡片样式生效，但不污染全局）
head = soup.find('head')
for macd_style in macd_soup.find_all('style'):
    raw_css = macd_style.string or macd_style.get_text() or ''
    scoped_css = scope_css(raw_css, f'.{SCOPE_CLASS}')
    new_style = soup.new_tag('style')
    new_style.string = scoped_css
    head.append(new_style)
print(f'已合并 {len(macd_soup.find_all("style"))} 个 <style> 到 head（scope: .{SCOPE_CLASS}）')

# 5. 创建新 panel，把 MACD body 内容包进去
new_panel = soup.new_tag('div', attrs={'id': f'tab-{TAB_ID}', 'class': 'panel'})
# scope 容器，包住所有 MACD 内容（让 scope 后的 CSS 生效）
scope_wrapper = soup.new_tag('div', attrs={'class': SCOPE_CLASS,
                                            'style': 'background:#0f172a;padding:20px;border-radius:8px;'})
hint = soup.new_tag('div', attrs={'style': 'background:white;padding:10px;border-radius:8px;margin-bottom:15px;color:#333;'})
hint.string = f'💡 这里是 MACD 滚动报告（v2.0）完整页面，生成于 {_today_iso()}'
scope_wrapper.append(hint)
# 把 macd_body 里的所有子元素搬过来（避免 body 标签嵌套）
import copy as _copy
for child in list(macd_body.children):
    scope_wrapper.append(_copy.copy(child))
new_panel.append(scope_wrapper)
# 把新 panel 加到 body 末尾（script 之前）
body = soup.find('body')
script_tag = soup.find('script')
if script_tag:
    script_tag.insert_before(new_panel)
else:
    body.append(new_panel)
print(f'已插入新 panel（含 {len(list(scope_wrapper.children))} 个 MACD body 子元素，scope: .{SCOPE_CLASS}）')

# 6. 写回
out_html = str(soup)
with open(DASHBOARD, 'w', encoding='utf-8') as f:
    f.write(out_html)
print(f'已写入: {DASHBOARD}')
print(f'  新文件大小: {os.path.getsize(DASHBOARD) / 1024:.1f} KB')
