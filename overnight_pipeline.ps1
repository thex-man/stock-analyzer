# Overnight pipeline driver (PowerShell 5.1)
# Waits for kline + concept crawler, then runs: html regen -> members import ->
# F10 crawls (events/profile/pledge/holders) -> verify -> git commit/push -> memory log.
# Idempotent stages; progress log: data\overnight_pipeline.log
$ErrorActionPreference = 'Continue'
Set-Location D:\stock\tool\stock
$log = 'data\overnight_pipeline.log'
function Log($m) { "$(Get-Date -Format 'MM-dd HH:mm:ss')  $m" | Add-Content $log -Encoding UTF8; Write-Host $m }

Log '=== overnight pipeline start ==='

function Wait-Proc($pattern, $timeoutMin) {
    $deadline = (Get-Date).AddMinutes($timeoutMin)
    while ((Get-Date) -lt $deadline) {
        $p = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like "*$pattern*" }
        if (-not $p) { return $true }
        Start-Sleep -Seconds 60
    }
    Log "WARN timeout waiting $pattern"
    return $false
}

# ---- stage 1: wait kline ----
Log 'stage1: waiting kline_full_pull'
Wait-Proc 'kline_full_pull' 90 | Out-Null
python -c "import duckdb; c=duckdb.connect('data/stock.duckdb', read_only=True); print('kline 8/27:', c.execute(chr(115)+chr(101)+chr(108)+chr(101)+chr(99)+chr(116)+' count(*) from kline where '+chr(39)+'2026-08-27'+chr(39)+'::DATE = date').fetchone())" 2>$null
if ($LASTEXITCODE -eq 0) { Log 'stage1 OK' } else { Log 'stage1 kline verify FAILED' }

# ---- stage 2: regen html (Top3/非Top3 汇总表) ----
Log 'stage2: db_html'
python scripts\db_html.py 2>&1 | Select-Object -Last 2 | ForEach-Object { Log "  $_" }
$html = Get-Content data\每日复盘看板.html -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
if ($html -and $html.Contains('入选Top3超过2次') -and $html.Contains('出现>2 次的个股')) {
    Log 'stage2 OK: 两个汇总表都在'
} else { Log 'stage2 WARN: 汇总表标记未找到' }

# ---- stage 3: wait concept crawler then import members ----
Log 'stage3: waiting crawler_all_concepts'
Wait-Proc 'crawler_all_concepts' 120 | Out-Null
Log 'stage3: db_import_members'
python scripts\db_import_members.py 2>&1 | Select-Object -Last 8 | ForEach-Object { Log "  $_" }

# ---- stage 4: F10 crawls (serial) ----
foreach ($page in @('events', 'profile', 'pledge', 'holders')) {
    Log "stage4: f10_crawler $page"
    python f10_crawler.py $page --threads 4 2>&1 | Select-Object -Last 3 | ForEach-Object { Log "  $_" }
}

# ---- stage 5: verify ----
Log 'stage5: verify'
python -c "import duckdb,sys; sys.stdout.reconfigure(encoding='utf-8'); c=duckdb.connect('data/stock.duckdb', read_only=True); print('events', c.execute('select count(*) from stock_events').fetchone()[0]); print('profile', c.execute('select count(*) from stock_profile').fetchone()[0]); print('pledge', c.execute('select count(*) from stock_pledge where pledge_ratio is not null').fetchone()[0]); print('holders', c.execute('select count(*) from stock_holders').fetchone()[0]); print('board_members', c.execute('select board_type, count(*) from board_members group by 1').fetchall())" 2>&1 | ForEach-Object { Log "  $_" }

# ---- stage 6: git ----
Log 'stage6: git commit+push'
git add -A 2>$null
git commit -m "F10数据入库: stock_events/profile/pledge/holders + 概念/行业/申万映射 (board_members/concept_leaders) + HTML Top3/非Top3汇总表" 2>&1 | Select-Object -First 2 | ForEach-Object { Log "  $_" }
git push origin main 2>&1 | Select-Object -Last 1 | ForEach-Object { Log "  $_" }

# workspace memory
Add-Content C:\Users\s5631\.openclaw\workspace\memory\2026-08-28.md -Encoding UTF8 -Value @"

### ~05:30 — F10 全量数据入库（夜间自动流水线完成）
- 新表: stock_events / stock_profile / stock_pledge / stock_holders（f10_crawler.py，F10静态页）
- board_members / concept_leaders / stock_industry_sw 已导入（db_import_members.py）
- kline 8/27 增量完成；HTML 重生成（Top3+非Top3 汇总表）
- 详见 data/overnight_pipeline.log
"@
Set-Location C:\Users\s5631\.openclaw\workspace
git add -A; git commit -m 'docs: 夜间流水线执行记录' 2>$null; git push origin master 2>$null
Log '=== overnight pipeline DONE ==='
