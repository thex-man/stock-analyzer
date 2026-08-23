with open('tgb_find.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Find main content area
markers = ['class="main"', 'class="main-content"', 'id="main"', 'class="container"', 'class="content"']
for m in markers:
    idx = html.find(m)
    if idx > 0:
        print(f'Found {m} at {idx}:')
        print(html[idx:idx+2500])
        print('---')
        break
else:
    # Show middle of page
    mid = len(html) // 2
    print('No main markers, showing middle:')
    print(html[mid-1500:mid+2500])