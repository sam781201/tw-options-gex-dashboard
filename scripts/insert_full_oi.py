"""Idempotent insertion of the full-strike panel into existing v11 index.html.
Do not replace or change any existing forecast, GEX/VEX, or OI comparison code.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
index = ROOT / "docs/index.html"
panel = ROOT / "docs/full_oi.html"
if not index.exists() or not panel.exists():
    raise SystemExit("找不到 docs/index.html 或 docs/full_oi.html；請確認已上傳兩個檔案。")
html = index.read_text(encoding="utf-8")
marker = 'id="fullOIMapV12"'
if marker in html:
    print("全市場履約價圖已存在，不重複插入。")
    raise SystemExit(0)

if 'id="levelsChart"' not in html or 'id="compareLevelChart"' not in html:
    raise SystemExit("找不到 v11 近端圖表結構，拒絕修改，以免破壞既有功能。")

# v11 already has one section for today’s levels and a following comparison section.
anchor = r'(<section\b[^>]*>\s*<h2>昨日／今日候選價位與 OI 變化</h2>)'
match = re.search(anchor, html)
if not match:
    raise SystemExit("找不到『昨日／今日候選價位與 OI 變化』區塊，拒絕修改。")

newpanel = '''<section class="card" id="fullOIMapV12">
<h2>全市場履約價 OI 分布｜包含 40,000 以下</h2>
<p class="muted">上方是近期第一、第二支撐壓力；此處顯示同到期別的完整履約價。可直接縮放、切換至 40,000 以下。兩張圖用途不同，遠方 OI 不直接視為近期支撐。</p>
<iframe src="./full_oi.html?v=12" title="全市場履約價 Call Put OI 分布圖" loading="lazy" style="display:block;width:100%;height:970px;border:1px solid #344d69;border-radius:10px;background:#122139" referrerpolicy="same-origin"></iframe>
</section>
'''
html = html[:match.start()] + newpanel + html[match.start():]
index.write_text(html, encoding="utf-8")
print("已加入完整履約價地圖：首頁近端圖保留，全市場圖放在昨日／今日比較之前。")
