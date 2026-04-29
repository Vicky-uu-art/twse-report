#!/usr/bin/env python3
"""
台股每日成交金額前30名 自動報表產生器
資料來源：台灣證交所 Open API、鉅亨網、Yahoo股市、UDN聯合新聞網
"""

import json
import re
import sys
import time
import requests
from datetime import date
from pathlib import Path

# ─────────────────────────────────────────────
# ETF / 槓桿ETF / 反向ETF / 權證 代碼識別
# ─────────────────────────────────────────────
def is_etf_or_warrant(code: str) -> bool:
    if re.search(r'[A-Za-z]', code) and len(code) >= 5:
        return True
    if code.startswith('00'):
        return True
    if code.startswith('009'):
        return True
    return False


# ─────────────────────────────────────────────
# 概念股對照表
# ─────────────────────────────────────────────
CONCEPT_MAP = {
    "2330": ["半導體", "晶圓代工", "AI晶片", "CoWoS先進封裝", "台灣護國神山"],
    "2303": ["半導體", "晶圓代工"],
    "2344": ["半導體", "記憶體", "DRAM"],
    "2337": ["半導體", "記憶體", "NOR Flash", "AI邊緣運算"],
    "2408": ["半導體", "記憶體", "DRAM", "HBM"],
    "6770": ["半導體", "晶圓代工", "特殊製程"],
    "5347": ["半導體", "矽晶圓"],
    "3711": ["半導體", "封裝測試", "先進封裝", "CoWoS"],
    "2379": ["半導體", "封裝測試"],
    "3034": ["半導體", "封裝測試"],
    "2449": ["半導體", "封裝測試", "IC測試", "AI晶片測試", "ASIC測試", "CoPoS"],
    "2454": ["IC設計", "半導體", "AI手機晶片", "MediaTek"],
    "2388": ["IC設計", "半導體", "驅動IC"],
    "3443": ["IC設計", "半導體", "AI晶片"],
    "3661": ["IC設計", "半導體", "AI晶片", "ASIC"],
    "3529": ["IC設計", "半導體", "嵌入式記憶體"],
    "2327": ["被動元件", "IC設計"],
    "3006": ["IC設計", "記憶體", "SRAM", "DRAM", "NOR Flash", "車用電子", "AI記憶體"],
    "2313": ["PCB", "電路板", "AI伺服器", "ABF載板"],
    "3189": ["PCB", "電路板", "ABF載板"],
    "3037": ["PCB", "電路板", "ABF載板"],
    "2368": ["PCB", "電路板"],
    "6269": ["PCB", "電路板", "ABF載板"],
    "2383": ["PCB材料", "覆銅板CCL", "AI伺服器"],
    "8046": ["PCB", "電路板", "ABF載板", "南亞電路板", "AI伺服器"],
    "2308": ["電源管理", "AI伺服器", "散熱", "電動車"],
    "3017": ["散熱模組", "AI伺服器散熱", "液冷"],
    "6669": ["雲端伺服器", "AI伺服器", "ODM"],
    "3665": ["線纜", "AI伺服器", "電子零組件"],
    "6515": ["連接器", "AI伺服器"],
    "3653": ["導線架", "AI晶片散熱", "半導體"],
    "6414": ["散熱", "AI伺服器"],
    "3596": ["散熱", "AI伺服器", "液冷"],
    "7769": ["半導體設備", "IC自動化測試設備", "AI晶片測試", "封測設備"],
    "2345": ["網通設備", "AI資料中心交換器", "乙太網路"],
    "4904": ["電信", "網通", "5G"],
    "2412": ["電信", "5G", "網通"],
    "4967": ["記憶體模組", "DRAM模組", "SSD", "AI記憶體"],
    "2609": ["航運", "貨櫃輪", "海運"],
    "2603": ["航運", "貨櫃輪", "海運"],
    "2615": ["航運", "貨櫃輪"],
    "2614": ["航運", "貨櫃輪"],
    "1303": ["石化", "塑化"],
    "1301": ["石化", "塑化"],
    "1326": ["石化", "塑化"],
    "2002": ["鋼鐵", "原物料"],
    "1802": ["玻璃", "太陽能玻璃", "中概內需"],
    "3036": ["電子通路", "IC代理"],
    "2347": ["電子通路", "IC代理"],
    "2882": ["金融", "壽險", "銀行"],
    "2881": ["金融", "壽險", "銀行"],
    "2891": ["金融", "銀行"],
    "2886": ["金融", "銀行"],
    "2884": ["金融", "金控"],
    "2885": ["金融", "金控"],
    "2892": ["金融", "銀行"],
    "2883": ["金融", "金控"],
    "2880": ["金融", "銀行"],
    "2887": ["金融", "金控"],
    "2890": ["金融", "金控"],
    "2317": ["EMS代工", "AI伺服器", "電動車", "鴻海生態系"],
    "2354": ["EMS代工", "鴻海生態系"],
    "3231": ["EMS代工", "鴻海生態系"],
    "6443": ["太陽能", "綠能"],
    "3576": ["太陽能", "綠能"],
    "3450": ["光通訊", "半導體", "AI資料中心"],
    "4977": ["光通訊", "AI資料中心"],
    "3491": ["光通訊", "AI資料中心"],
    "2357": ["電腦整機", "筆電", "AI PC"],
    "2382": ["筆電代工", "AI PC"],
    "2353": ["電腦整機", "AI PC"],
    "4958": ["連接器", "AI伺服器", "PCB"],
    "6176": ["連接器", "AI伺服器"],
    "2352": ["網路設備", "ODM"],
    "3008": ["光學鏡頭", "車用鏡頭"],
    "2474": ["機殼", "iPhone供應鏈"],
    "2356": ["伺服器", "AI伺服器", "ODM"],
    "3045": ["電信", "5G"],
}

def get_concepts(code):
    return CONCEPT_MAP.get(code, ["其他"])


# ─────────────────────────────────────────────
# 抓取證交所資料
# ─────────────────────────────────────────────
def fetch_twse_value30(target_date):
    url = (f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
           f"?date={target_date}&type=ALLBUT0999&response=json")
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.twse.com.tw/"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] {e}")
        return []
    if data.get("stat") != "OK":
        print(f"[WARN] {data.get('stat')}")
        return []

    results = []
    for table in data.get("tables", []):
        fields = table.get("fields", [])
        rows   = table.get("data",   [])
        if "成交金額" not in fields:
            continue
        def fi(n): return fields.index(n) if n in fields else None
        ic, nm, cl, vl, am, cg = fi("證券代號"), fi("證券名稱"), fi("收盤價"), fi("成交股數"), fi("成交金額"), fi("漲跌價差")
        for row in rows:
            try:
                code = row[ic].strip()
                if is_etf_or_warrant(code):
                    continue
                name  = row[nm].strip()
                close = row[cl].replace(",","").strip()
                vol   = row[vl].replace(",","").strip()
                amt   = row[am].replace(",","").strip()
                chg   = row[cg].replace(",","").strip()
                amt_i = int(amt) if amt.lstrip("-").isdigit() else 0
                if amt_i <= 0: continue
                vol_k  = int(vol)//1000 if vol.isdigit() else 0
                amt_yi = amt_i/1e8
                try:
                    cf, gf = float(close), float(chg)
                    base = cf - gf
                    pct  = (gf/base)*100 if base else 0
                except:
                    gf, pct = 0, 0
                results.append({"code":code,"name":name,"close":close,"volume":vol_k,
                                 "amount":amt_yi,"change":gf,"change_pct":round(pct,2),
                                 "concepts":get_concepts(code)})
            except:
                continue
    results.sort(key=lambda x: x["amount"], reverse=True)
    top30 = results[:30]
    for i,r in enumerate(top30): r["rank"]=i+1
    return top30


# ─────────────────────────────────────────────
# 新聞抓取
# ─────────────────────────────────────────────
def fetch_cnyes_news(code, name, max_news=3):
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news?limit=20&page=1&symbol={code}"
    headers = {"User-Agent":"Mozilla/5.0","Referer":f"https://www.cnyes.com/twstock/{code}","Origin":"https://www.cnyes.com"}
    today_str = date.today().strftime("%Y-%m-%d")
    try:
        data  = requests.get(url, headers=headers, timeout=10).json()
        items = data.get("items",{}).get("data",[])
        news  = []
        for item in items:
            if today_str not in str(item.get("publishAt","")): continue
            title, nid = item.get("title",""), item.get("newsId","")
            link = f"https://news.cnyes.com/news/id/{nid}" if nid else ""
            if title and link: news.append({"title":title,"link":link,"source":"鉅亨網"})
            if len(news)>=max_news: break
        return news
    except:
        return []

def fetch_yahoo_news(code, name, max_news=2):
    url = f"https://tw.stock.yahoo.com/quote/{code}.TW/news"
    headers = {"User-Agent":"Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36","Accept-Language":"zh-TW"}
    try:
        html = requests.get(url, headers=headers, timeout=10).text
        news, seen = [], set()
        for title, link in re.findall(r'"title":"([^"]+)","url":"(https://[^"]+)"', html):
            if title in seen: continue
            seen.add(title)
            if name in title or code in link:
                news.append({"title":title,"link":link,"source":"Yahoo股市"})
            if len(news)>=max_news: break
        return news
    except:
        return []

def fetch_udn_news(code, name, max_news=2):
    url = f"https://udn.com/search/result/2/{name}"
    headers = {"User-Agent":"Mozilla/5.0","Accept-Language":"zh-TW","Referer":"https://udn.com/"}
    try:
        html = requests.get(url, headers=headers, timeout=10).text
        news, seen = [], set()
        for link, title in re.findall(r'href="(https://udn\.com/news/story/[^"]+)"[^>]*>([^<]{8,})</a>', html):
            title = title.strip()
            if title in seen or len(title)<8: continue
            seen.add(title)
            if name in title or code in title:
                news.append({"title":title,"link":link,"source":"聯合新聞網"})
            if len(news)>=max_news: break
        return news
    except:
        return []

def fetch_all_news(code, name):
    all_news, seen = [], set()
    for n in fetch_cnyes_news(code,name,3)+fetch_yahoo_news(code,name,2)+fetch_udn_news(code,name,2):
        if n["title"] not in seen:
            seen.add(n["title"])
            all_news.append(n)
    return all_news[:5]


# ─────────────────────────────────────────────
# 讀前一日資料
# ─────────────────────────────────────────────
def load_previous_data(data_dir):
    files = sorted(data_dir.glob("*.json"), reverse=True)
    if not files: return {}
    try:
        with open(files[0], encoding="utf-8") as f:
            prev = json.load(f)
        return {s["code"]:{"rank":s.get("rank",99),"concepts":set(s.get("concepts",[]))}
                for s in prev.get("stocks",[])}
    except:
        return {}


# ─────────────────────────────────────────────
# 產生 HTML（淺色主題）
# ─────────────────────────────────────────────
def generate_html(stocks, prev_data, report_date, all_dates):
    prev_codes, prev_concepts = set(prev_data.keys()), set()
    for v in prev_data.values(): prev_concepts.update(v.get("concepts",set()))
    today_concepts = set()
    for s in stocks: today_concepts.update(s["concepts"])
    new_concepts = today_concepts - prev_concepts

    bar_labels  = [f"{s['name']} {s['code']}" for s in stocks]
    bar_amounts = [round(s["amount"],2) for s in stocks]
    bar_colors  = ["#f59e0b" if (s["code"] not in prev_codes and prev_codes)
                   else "#f97316" if set(s["concepts"]) & new_concepts
                   else "#3b82f6" for s in stocks]

    nav_links = "".join(
        f'<a href="{d}.html" class="nav-date{"  active" if d==report_date else ""}">{d}</a>\n'
        for d in all_dates[:10]
    )

    rows_html = ""
    for s in stocks:
        is_new   = s["code"] not in prev_codes and bool(prev_codes)
        new_tags = set(s["concepts"]) & new_concepts if new_concepts else set()
        row_cls  = "new-stock" if is_new else ("new-concept" if new_tags else "")
        badges   = (('<span class="badge badge-new">★ 新進榜</span>' if is_new else "") +
                    "".join(f'<span class="badge badge-concept">🔥 新概念：{c}</span>' for c in new_tags))
        tags     = " ".join(f'<span class="tag {"tag-hl" if c in new_concepts else ""}">{c}</span>'
                            for c in s["concepts"])
        pct      = s.get("change_pct",0)
        arrow    = "▲" if pct>0 else ("▼" if pct<0 else "─")
        chg_cls  = "up" if pct>0 else ("dn" if pct<0 else "flat")
        news_html = "".join(
            f'<div class="ni"><span class="nsrc">{n["source"]}</span>'
            f'<a href="{n["link"]}" target="_blank">{n["title"]}</a></div>'
            for n in s.get("news",[])
        ) or '<div class="ni empty">— 今日無相關新聞 —</div>'
        rows_html += f"""
<tr class="{row_cls}">
  <td class="rank">#{s['rank']}</td>
  <td class="code">{s['code']}</td>
  <td class="name">{s['name']}{badges}<div class="news-block">{news_html}</div></td>
  <td class="price">{s['close']}</td>
  <td class="vol">{s['volume']:,}</td>
  <td class="amt"><strong>{s['amount']:.2f}</strong></td>
  <td class="tags">{tags}</td>
  <td class="chg {chg_cls}">{arrow} {abs(pct):.2f}%</td>
</tr>"""

    total     = sum(s["amount"] for s in stocks)
    new_count = sum(1 for s in stocks if s["code"] not in prev_codes and prev_codes)

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>台股成交金額前30名 — {report_date}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#f8fafc;color:#1e293b;font-family:-apple-system,"Noto Sans TC",sans-serif;padding:24px;font-size:14px}}
h1{{font-size:1.5rem;font-weight:700;color:#0f172a;margin-bottom:4px}}
.sub{{color:#64748b;font-size:.82rem;margin-bottom:20px}}
.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}
.sc{{background:#fff;border:1px solid #e2e8f0;border-radius:10px;padding:12px 18px;min-width:148px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.sc-label{{font-size:.7rem;color:#94a3b8;margin-bottom:3px}}.sc-val{{font-size:1.2rem;font-weight:700;color:#2563eb}}
.date-nav{{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:20px;align-items:center}}
.date-nav span{{font-size:.78rem;color:#94a3b8}}
.nav-date{{background:#fff;border:1px solid #e2e8f0;color:#475569;padding:4px 10px;border-radius:6px;text-decoration:none;font-size:.78rem;transition:.15s}}
.nav-date:hover,.nav-date.active{{background:#2563eb;color:#fff;border-color:#2563eb}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;font-size:.78rem;color:#475569}}
.ld{{display:flex;align-items:center;gap:5px}}.ldot{{width:11px;height:11px;border-radius:2px}}
.chart-card{{background:#fff;border:1px solid #e2e8f0;border-radius:12px;padding:16px;margin-bottom:24px;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.chart-card h2{{font-size:.82rem;color:#94a3b8;margin-bottom:10px}}.chart-wrap{{height:300px}}
.table-wrap{{overflow-x:auto;border-radius:12px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
table{{width:100%;border-collapse:collapse;background:#fff;font-size:.83rem}}
th{{background:#f1f5f9;color:#64748b;padding:9px 12px;text-align:left;font-weight:600;border-bottom:1px solid #e2e8f0;position:sticky;top:0}}
td{{padding:9px 12px;border-bottom:1px solid #f1f5f9;vertical-align:top}}
tr:hover td{{background:#f8fafc}}
tr.new-stock td{{background:#fffbeb}}tr.new-concept td{{background:#fff7ed}}
.rank{{font-weight:700;color:#94a3b8;width:40px}}.code{{font-family:monospace;color:#2563eb;font-weight:600;width:58px}}
.name{{max-width:210px;line-height:1.5}}.price,.vol,.amt{{text-align:right}}
.amt strong{{color:#1d4ed8}}.tags{{max-width:190px}}
.chg{{text-align:right;font-weight:600;width:78px}}
.up{{color:#16a34a}}.dn{{color:#dc2626}}.flat{{color:#94a3b8}}
.badge{{display:inline-block;font-size:.65rem;padding:2px 5px;border-radius:3px;margin:2px 2px 2px 0;font-weight:600}}
.badge-new{{background:#fef3c7;color:#92400e;border:1px solid #fcd34d}}
.badge-concept{{background:#ffedd5;color:#9a3412;border:1px solid #fdba74}}
.tag{{display:inline-block;font-size:.68rem;background:#eff6ff;color:#1d4ed8;padding:1px 5px;border-radius:3px;margin:2px 2px 1px 0;border:1px solid #bfdbfe}}
.tag-hl{{background:#fef3c7;color:#92400e;border-color:#fcd34d}}
.news-block{{margin-top:4px}}
.ni{{font-size:.74rem;color:#64748b;margin:3px 0;line-height:1.4}}
.ni a{{color:#2563eb;text-decoration:none}}.ni a:hover{{text-decoration:underline}}
.nsrc{{display:inline-block;font-size:.63rem;background:#eff6ff;color:#1d4ed8;padding:1px 4px;border-radius:2px;margin-right:3px;border:1px solid #bfdbfe}}
.ni.empty{{color:#cbd5e1;font-size:.7rem}}
</style>
</head>
<body>
<h1>📊 台股每日成交金額前30名</h1>
<div class="sub">資料日期：{report_date}　資料來源：台灣證交所 ＋ 鉅亨網 ＋ Yahoo股市 ＋ 聯合新聞網　｜　已排除 ETF 及權證</div>
<div class="stats">
  <div class="sc"><div class="sc-label">前30名合計成交金額</div><div class="sc-val">{total:.0f} 億</div></div>
  <div class="sc"><div class="sc-label">今日新進榜個股</div><div class="sc-val">{new_count} 檔</div></div>
  <div class="sc"><div class="sc-label">今日新出現概念股</div><div class="sc-val">{len(new_concepts)} 個</div></div>
</div>
<div class="date-nav"><span>歷史：</span>{nav_links}<a href="index.html" class="nav-date">📋 全部</a></div>
<div class="legend">
  <div class="ld"><div class="ldot" style="background:#3b82f6"></div>一般個股</div>
  <div class="ld"><div class="ldot" style="background:#f59e0b"></div>🟡 今日新進榜</div>
  <div class="ld"><div class="ldot" style="background:#f97316"></div>🟠 新概念族群</div>
</div>
<div class="chart-card">
  <h2>成交金額（億元）— 前30名分布</h2>
  <div class="chart-wrap"><canvas id="bar"></canvas></div>
</div>
<div class="table-wrap">
<table>
  <thead><tr><th>排名</th><th>代碼</th><th>名稱 / 新聞</th><th>收盤價</th><th>成交張數</th><th>成交金額(億)</th><th>所屬概念股</th><th>漲跌幅</th></tr></thead>
  <tbody>{rows_html}</tbody>
</table>
</div>
<script>
new Chart(document.getElementById('bar'),{{
  type:'bar',
  data:{{labels:{json.dumps(bar_labels,ensure_ascii=False)},datasets:[{{data:{json.dumps(bar_amounts)},backgroundColor:{json.dumps(bar_colors)},borderRadius:3}}]}},
  options:{{responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>c.parsed.y.toFixed(2)+' 億'}}}}}},
    scales:{{x:{{ticks:{{color:'#94a3b8',font:{{size:10}},maxRotation:45}},grid:{{color:'#f1f5f9'}}}},
             y:{{ticks:{{color:'#94a3b8',callback:v=>v+'億'}},grid:{{color:'#f1f5f9'}}}}}}}}
}});
</script>
</body></html>"""


def generate_index_html(all_dates):
    links = "".join(f'<a href="{d}.html" class="dl">📅 {d}</a>\n' for d in all_dates)
    return f"""<!DOCTYPE html><html lang="zh-TW"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>台股成交金額報表 — 歷史總覽</title>
<style>body{{background:#f8fafc;color:#1e293b;font-family:-apple-system,"Noto Sans TC",sans-serif;padding:32px;max-width:680px;margin:auto}}
h1{{font-size:1.4rem;margin-bottom:6px}}p{{color:#64748b;margin-bottom:24px;font-size:.88rem}}
.dl{{display:block;background:#fff;border:1px solid #e2e8f0;color:#2563eb;padding:10px 16px;border-radius:8px;text-decoration:none;margin-bottom:7px;font-size:.88rem;transition:.15s}}
.dl:hover{{background:#eff6ff}}</style></head>
<body><h1>📊 台股每日成交金額前30名 — 歷史總覽</h1>
<p>共 {len(all_dates)} 份報表，點選日期查看當日詳細報表</p>{links}</body></html>"""


# ─────────────────────────────────────────────
# 主程式
# ─────────────────────────────────────────────
def main():
    base_dir    = Path(__file__).parent.parent
    data_dir    = base_dir / "data"
    reports_dir = base_dir / "reports"
    data_dir.mkdir(exist_ok=True)
    reports_dir.mkdir(exist_ok=True)

    today       = date.today()
    report_date = today.strftime("%Y-%m-%d")
    twse_date   = today.strftime("%Y%m%d")

    print(f"[{report_date}] 開始抓取（排除ETF/權證）...")
    stocks = fetch_twse_value30(twse_date)
    if not stocks:
        print("[ERROR] 無資料，可能休市或未更新")
        sys.exit(1)
    print(f"  ✓ {len(stocks)} 筆個股")

    print("  抓取新聞（鉅亨 + Yahoo + UDN）...")
    for s in stocks:
        s["news"] = fetch_all_news(s["code"], s["name"])
        time.sleep(0.4)
        print(f"    {s['code']} {s['name']}: {len(s['news'])} 則")

    prev_data = load_previous_data(data_dir)
    print(f"  ✓ 前日資料 {len(prev_data)} 檔")

    with open(data_dir/f"{report_date}.json","w",encoding="utf-8") as f:
        json.dump({"date":report_date,"stocks":[{k:(list(v) if isinstance(v,set) else v)
            for k,v in s.items() if k!="news"} for s in stocks]},f,ensure_ascii=False,indent=2)

    all_dates = sorted(
        {f.stem for f in reports_dir.glob("????-??-??.html")} | {report_date}, reverse=True)

    with open(reports_dir/f"{report_date}.html","w",encoding="utf-8") as f:
        f.write(generate_html(stocks, prev_data, report_date, all_dates))
    with open(reports_dir/"index.html","w",encoding="utf-8") as f:
        f.write(generate_index_html(all_dates))

    print(f"  ✓ 報表完成：reports/{report_date}.html")


if __name__ == "__main__":
    main()
