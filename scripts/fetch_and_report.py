#!/usr/bin/env python3
"""
台股每日成交金額前30名 自動報表產生器
資料來源：台灣證交所 Open API、鉅亨網新聞、Yahoo股市新聞
"""

import json
import os
import sys
import time
import requests
from datetime import datetime, date, timedelta
from pathlib import Path
import re

# ─────────────────────────────────────────────
# 概念股對照表（內建）
# ─────────────────────────────────────────────
CONCEPT_MAP = {
    # 半導體 / 晶圓代工
    "2330": ["半導體", "晶圓代工", "AI晶片", "CoWoS先進封裝", "台灣護國神山"],
    "2303": ["半導體", "晶圓代工", "記憶體"],
    "2344": ["半導體", "記憶體", "DRAM"],
    "2337": ["半導體", "記憶體", "NOR Flash", "AI邊緣運算"],
    "2408": ["半導體", "記憶體", "DRAM", "HBM"],
    "6770": ["半導體", "晶圓代工", "特殊製程"],
    "5347": ["半導體", "矽晶圓"],
    "3711": ["半導體", "封裝測試", "先進封裝"],
    "2379": ["半導體", "封裝測試"],
    "3034": ["半導體", "封裝測試"],
    # IC 設計
    "2454": ["IC設計", "半導體", "AI手機晶片", "MediaTek"],
    "2388": ["IC設計", "半導體", "驅動IC"],
    "3443": ["IC設計", "半導體", "AI晶片"],
    "3661": ["IC設計", "半導體", "AI晶片", "ASIC"],
    "3529": ["IC設計", "半導體", "嵌入式記憶體"],
    "2327": ["被動元件", "IC設計"],
    # PCB / 載板
    "2313": ["PCB", "電路板", "AI伺服器", "ABF載板"],
    "3189": ["PCB", "電路板", "ABF載板"],
    "3037": ["PCB", "電路板", "ABF載板"],
    "2368": ["PCB", "電路板"],
    "6269": ["PCB", "電路板", "ABF載板"],
    "2383": ["PCB材料", "覆銅板CCL", "AI伺服器"],
    # AI 伺服器 / 散熱 / 電源
    "2308": ["電源管理", "AI伺服器", "散熱", "電動車"],
    "3017": ["散熱模組", "AI伺服器散熱", "液冷"],
    "6669": ["雲端伺服器", "AI伺服器", "ODM"],
    "3665": ["線纜", "AI伺服器", "電子零組件"],
    "6515": ["連接器", "AI伺服器"],
    "3653": ["導線架", "AI晶片散熱", "半導體"],
    "6414": ["散熱", "AI伺服器"],
    "3596": ["散熱", "AI伺服器", "液冷"],
    # 網通
    "2345": ["網通設備", "AI資料中心交換器", "乙太網路"],
    "4904": ["電信", "網通", "5G"],
    "2412": ["電信", "5G", "網通"],
    # 航運
    "2609": ["航運", "貨櫃輪", "海運"],
    "2603": ["航運", "貨櫃輪", "海運"],
    "2615": ["航運", "貨櫃輪"],
    "2614": ["航運", "貨櫃輪"],
    # 石化 / 原物料
    "1303": ["石化", "塑化"],
    "1301": ["石化", "塑化"],
    "1326": ["石化", "塑化"],
    "2002": ["鋼鐵", "原物料"],
    # 電子通路 / 代理
    "3036": ["電子通路", "IC代理"],
    "2347": ["電子通路", "IC代理"],
    # 金融
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
    # ETF
    "0050": ["ETF", "台灣50", "指數型ETF"],
    "0056": ["ETF", "高股息ETF"],
    "00631L": ["ETF", "槓桿型ETF", "台灣50正2"],
    "00919": ["ETF", "高股息ETF"],
    "00929": ["ETF", "高股息ETF"],
    "00878": ["ETF", "高股息ETF"],
    # 鴻海生態系
    "2317": ["EMS代工", "AI伺服器", "電動車", "鴻海生態系"],
    "2354": ["EMS代工", "鴻海生態系"],
    "3231": ["EMS代工", "鴻海生態系"],
    # 太陽能
    "6443": ["太陽能", "綠能"],
    "3576": ["太陽能", "綠能"],
    # 光通訊
    "3450": ["光通訊", "半導體", "AI資料中心"],
    "4977": ["光通訊", "AI資料中心"],
    "3491": ["光通訊", "AI資料中心"],
    # 其他
    "2357": ["電腦整機", "筆電", "AI PC"],
    "2382": ["筆電代工", "AI PC"],
    "4958": ["連接器", "AI伺服器"],
    "6176": ["連接器", "AI伺服器"],
    "2352": ["網路設備", "ODM"],
    "3008": ["光學鏡頭", "車用鏡頭"],
    "2474": ["可成", "機殼", "iPhone供應鏈"],
    "2356": ["英業達", "伺服器", "AI伺服器"],
    "2353": ["宏碁", "電腦整機", "AI PC"],
    "3045": ["台灣大哥大", "電信", "5G"],
}

def get_concepts(stock_id):
    return CONCEPT_MAP.get(stock_id, ["其他"])

# ─────────────────────────────────────────────
# 抓取證交所成交金額前30名
# ─────────────────────────────────────────────
def fetch_twse_top30(target_date: str = None) -> list:
    """
    從證交所 Open API 抓取當日成交金額排行
    target_date: 'YYYYMMDD' 格式，預設今天
    """
    if not target_date:
        target_date = date.today().strftime("%Y%m%d")

    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX20?date={target_date}&response=json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": "https://www.twse.com.tw/"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] 無法取得證交所資料: {e}")
        return []

    if data.get("stat") != "OK":
        print(f"[WARN] 證交所回應狀態非OK: {data.get('stat')}")
        return []

    # 找成交金額排行表（table4 通常是成交金額前20，需要另外處理）
    # 改用另一個 endpoint 取得完整前30
    return fetch_twse_value30(target_date)


def fetch_twse_value30(target_date: str) -> list:
    """
    抓取成交金額前30名（使用成交量排行 endpoint 再補充資料）
    """
    # 先用每日收盤行情拿所有股票，再排序
    url = f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={target_date}&type=ALLBUT0999&response=json"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
        "Referer": "https://www.twse.com.tw/"
    }

    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] 無法取得每日行情: {e}")
        return []

    if data.get("stat") != "OK":
        print(f"[WARN] 狀態: {data.get('stat')}")
        return []

    results = []
    for table in data.get("tables", []):
        fields = table.get("fields", [])
        rows = table.get("data", [])
        # 找有"成交金額"欄位的表
        if "成交金額" not in fields:
            continue
        idx_code  = fields.index("證券代號") if "證券代號" in fields else 0
        idx_name  = fields.index("證券名稱") if "證券名稱" in fields else 1
        idx_close = fields.index("收盤價")   if "收盤價"   in fields else 6
        idx_vol   = fields.index("成交股數") if "成交股數" in fields else 2
        idx_amt   = fields.index("成交金額") if "成交金額" in fields else 4
        idx_chg   = fields.index("漲跌價差") if "漲跌價差" in fields else 9

        for row in rows:
            try:
                code  = row[idx_code].strip()
                name  = row[idx_name].strip()
                close = row[idx_close].replace(",", "").strip()
                vol   = row[idx_vol].replace(",", "").strip()
                amt   = row[idx_amt].replace(",", "").strip()
                chg   = row[idx_chg].replace(",", "").strip()

                amt_int = int(amt) if amt.isdigit() else 0
                if amt_int == 0:
                    continue

                # 成交張數 = 成交股數 / 1000
                vol_int = int(vol) if vol.isdigit() else 0
                vol_k   = vol_int // 1000

                # 成交金額（億）
                amt_yi = amt_int / 1e8

                # 漲跌幅（需要收盤價計算）
                try:
                    close_f = float(close)
                    chg_f   = float(chg)
                    chg_pct = (chg_f / (close_f - chg_f)) * 100 if (close_f - chg_f) != 0 else 0
                except:
                    chg_pct = 0
                    chg_f   = 0

                results.append({
                    "code":    code,
                    "name":    name,
                    "close":   close,
                    "volume":  vol_k,       # 張
                    "amount":  amt_yi,       # 億
                    "change":  chg_f,
                    "change_pct": round(chg_pct, 2),
                    "concepts": get_concepts(code),
                })
            except Exception:
                continue

    # 依成交金額排序，取前30
    results.sort(key=lambda x: x["amount"], reverse=True)
    top30 = results[:30]

    for i, r in enumerate(top30):
        r["rank"] = i + 1

    return top30


# ─────────────────────────────────────────────
# 抓取鉅亨網個股新聞
# ─────────────────────────────────────────────
def fetch_cnyes_news(code: str, name: str, max_news: int = 3) -> list:
    """
    從鉅亨網抓取個股當日新聞
    """
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news?limit=20&page=1&symbol={code}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Referer": f"https://www.cnyes.com/twstock/{code}",
        "Origin": "https://www.cnyes.com",
    }
    today_str = date.today().strftime("%Y-%m-%d")

    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        # fallback：直接搜尋
        return fetch_cnyes_news_fallback(code, name, max_news)

    news_list = []
    items = data.get("items", {}).get("data", [])
    for item in items:
        pub_date = item.get("publishAt", "")
        # 只取今日新聞
        if today_str not in str(pub_date):
            continue
        title = item.get("title", "")
        news_id = item.get("newsId", "")
        link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else ""
        if title and link:
            news_list.append({"title": title, "link": link, "source": "鉅亨網"})
        if len(news_list) >= max_news:
            break

    return news_list


def fetch_cnyes_news_fallback(code: str, name: str, max_news: int = 3) -> list:
    """備用：用搜尋方式取得鉅亨新聞"""
    url = f"https://api.cnyes.com/media/api/v1/newslist/category/tw_stock_news?limit=10&page=1&keyword={name}"
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.cnyes.com/"}
    today_str = date.today().strftime("%Y-%m-%d")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        data = resp.json()
        news_list = []
        for item in data.get("items", {}).get("data", []):
            pub_date = str(item.get("publishAt", ""))
            if today_str not in pub_date:
                continue
            title = item.get("title", "")
            news_id = item.get("newsId", "")
            link = f"https://news.cnyes.com/news/id/{news_id}" if news_id else ""
            if title and link:
                news_list.append({"title": title, "link": link, "source": "鉅亨網"})
            if len(news_list) >= max_news:
                break
        return news_list
    except Exception:
        return []


def fetch_yahoo_news(code: str, name: str, max_news: int = 3) -> list:
    """
    從 Yahoo 股市抓取個股新聞
    """
    url = f"https://tw.stock.yahoo.com/quote/{code}.TW/news"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }
    today_str = date.today().strftime("%Y/%m/%d")
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        html = resp.text
        # 簡單解析新聞標題和連結
        news_list = []
        # 找 news items (Yahoo 用 data-* 或 JSON in HTML)
        pattern = r'"title":"([^"]+)","url":"(https://[^"]+)"'
        matches = re.findall(pattern, html)
        seen = set()
        for title, link in matches:
            if title in seen:
                continue
            seen.add(title)
            # 過濾：確保包含股票名稱或代碼
            if name in title or code in title or code in link:
                news_list.append({"title": title, "link": link, "source": "Yahoo股市"})
            if len(news_list) >= max_news:
                break
        return news_list
    except Exception:
        return []


def fetch_all_news(code: str, name: str) -> list:
    """整合鉅亨網 + Yahoo 新聞"""
    news = []
    cnyes = fetch_cnyes_news(code, name, max_news=3)
    yahoo = fetch_yahoo_news(code, name, max_news=2)
    seen_titles = set()
    for n in cnyes + yahoo:
        if n["title"] not in seen_titles:
            seen_titles.add(n["title"])
            news.append(n)
    return news[:5]  # 最多5則


# ─────────────────────────────────────────────
# 讀取昨日資料（比較用）
# ─────────────────────────────────────────────
def load_previous_data(data_dir: Path) -> dict:
    """讀取最近一個交易日的資料，回傳 {code: {rank, concepts}} dict"""
    json_files = sorted(data_dir.glob("*.json"), reverse=True)
    if not json_files:
        return {}
    latest = json_files[0]
    try:
        with open(latest) as f:
            prev = json.load(f)
        result = {}
        for item in prev.get("stocks", []):
            result[item["code"]] = {
                "rank":     item.get("rank", 99),
                "concepts": set(item.get("concepts", [])),
            }
        return result
    except Exception:
        return {}


# ─────────────────────────────────────────────
# 產生 HTML 報表
# ─────────────────────────────────────────────
def generate_html(stocks: list, prev_data: dict, report_date: str, all_dates: list) -> str:
    """
    stocks: 今日前30名資料（含新聞）
    prev_data: 昨日資料 dict
    report_date: 'YYYY-MM-DD'
    all_dates: 所有歷史報表日期 list（從新到舊）
    """

    # 找出今日新進榜個股 & 新概念股
    prev_codes     = set(prev_data.keys())
    prev_concepts  = set()
    for v in prev_data.values():
        prev_concepts.update(v.get("concepts", set()))

    today_concepts = set()
    for s in stocks:
        today_concepts.update(s["concepts"])

    new_concepts = today_concepts - prev_concepts

    # 柱狀圖資料
    bar_labels  = [f"{s['name']}\n{s['code']}" for s in stocks]
    bar_amounts = [round(s["amount"], 2) for s in stocks]
    bar_colors  = []
    for s in stocks:
        if s["code"] not in prev_codes:
            bar_colors.append("#f59e0b")   # 新進榜 → 橘黃
        elif set(s["concepts"]) & new_concepts:
            bar_colors.append("#fb923c")   # 新概念股 → 橘
        else:
            bar_colors.append("#3b82f6")   # 一般 → 藍

    # 歷史導覽
    nav_links = ""
    for d in all_dates[:10]:  # 最近10天
        active = "active" if d == report_date else ""
        nav_links += f'<a href="{d}.html" class="nav-date {active}">{d}</a>\n'

    # 表格列
    rows_html = ""
    for s in stocks:
        is_new_stock   = s["code"] not in prev_codes and bool(prev_codes)
        new_concept_in = set(s["concepts"]) & new_concepts if new_concepts else set()

        row_class = ""
        badge_html = ""
        if is_new_stock:
            row_class  = "new-stock"
            badge_html += '<span class="badge badge-new-stock">★ 新進榜</span>'
        if new_concept_in:
            row_class   = row_class or "new-concept"
            for c in new_concept_in:
                badge_html += f'<span class="badge badge-new-concept">🔥 新概念：{c}</span>'

        concepts_html = " ".join(
            f'<span class="tag {"tag-highlight" if c in new_concepts else ""}">{c}</span>'
            for c in s["concepts"]
        )

        chg_pct   = s.get("change_pct", 0)
        chg_class = "up" if chg_pct > 0 else ("down" if chg_pct < 0 else "flat")
        chg_sign  = "▲" if chg_pct > 0 else ("▼" if chg_pct < 0 else "─")
        chg_str   = f"{chg_sign} {abs(chg_pct):.2f}%"

        # 新聞
        news_html = ""
        for n in s.get("news", []):
            src_badge = f'<span class="news-src">{n["source"]}</span>'
            news_html += f'<div class="news-item">{src_badge}<a href="{n["link"]}" target="_blank">{n["title"]}</a></div>'
        if not news_html:
            news_html = '<div class="news-empty">— 今日無相關新聞 —</div>'

        rows_html += f"""
        <tr class="{row_class}">
          <td class="rank">#{s['rank']}</td>
          <td class="code">{s['code']}</td>
          <td class="name">
            {s['name']}
            {badge_html}
            <div class="news-block">{news_html}</div>
          </td>
          <td class="price">{s['close']}</td>
          <td class="vol">{s['volume']:,}</td>
          <td class="amt"><strong>{s['amount']:.2f}</strong></td>
          <td class="concepts">{concepts_html}</td>
          <td class="chg {chg_class}">{chg_str}</td>
        </tr>"""

    total_amt = sum(s["amount"] for s in stocks)

    # Chart.js 資料
    bar_labels_js  = json.dumps(bar_labels,  ensure_ascii=False)
    bar_amounts_js = json.dumps(bar_amounts, ensure_ascii=False)
    bar_colors_js  = json.dumps(bar_colors,  ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股每日成交金額前30名 — {report_date}</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f172a; --card: #1e293b; --card2: #263148;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #3b82f6;
    --up: #22c55e; --down: #ef4444; --flat: #94a3b8;
    --new-stock: #fef3c7; --new-concept: #fff7ed;
    --highlight: #f59e0b;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, "Noto Sans TC", sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; margin-bottom: 20px; }}
  .stats {{ display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }}
  .stat-card {{ background: var(--card); border-radius: 10px; padding: 14px 20px; min-width: 160px; }}
  .stat-label {{ font-size: 0.75rem; color: var(--muted); margin-bottom: 4px; }}
  .stat-value {{ font-size: 1.3rem; font-weight: 700; color: var(--accent); }}
  /* 歷史導覽 */
  .date-nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 24px; }}
  .nav-date {{ background: var(--card); color: var(--muted); padding: 6px 12px; border-radius: 6px;
               text-decoration: none; font-size: 0.82rem; transition: all .2s; }}
  .nav-date:hover {{ background: var(--accent); color: #fff; }}
  .nav-date.active {{ background: var(--accent); color: #fff; }}
  /* 圖表 */
  .chart-card {{ background: var(--card); border-radius: 12px; padding: 20px; margin-bottom: 28px; }}
  .chart-card h2 {{ font-size: 1rem; color: var(--muted); margin-bottom: 16px; }}
  .chart-wrap {{ height: 340px; }}
  /* 表格 */
  .table-wrap {{ overflow-x: auto; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 0.88rem; }}
  th {{ background: var(--card2); color: var(--muted); padding: 10px 12px; text-align: left;
        position: sticky; top: 0; z-index: 2; }}
  td {{ padding: 10px 12px; border-bottom: 1px solid #1e293b; vertical-align: top; }}
  tr:hover td {{ background: #1a2744; }}
  tr.new-stock td {{ background: rgba(245,158,11,.08); }}
  tr.new-concept td {{ background: rgba(251,146,60,.06); }}
  .rank {{ font-weight: 700; color: var(--muted); width: 44px; }}
  .rank:nth-child(1) {{ color: #fbbf24; }}
  .code {{ font-family: monospace; color: var(--accent); width: 64px; }}
  .name {{ max-width: 240px; }}
  .name > b, .name > span {{ display: block; }}
  .price {{ text-align: right; width: 80px; }}
  .vol {{ text-align: right; width: 100px; color: var(--muted); }}
  .amt {{ text-align: right; width: 110px; color: var(--text); }}
  .amt strong {{ color: #60a5fa; font-size: 1rem; }}
  .concepts {{ max-width: 220px; }}
  .chg {{ text-align: right; width: 90px; font-weight: 600; }}
  .up {{ color: var(--up); }} .down {{ color: var(--down); }} .flat {{ color: var(--flat); }}
  /* Badge */
  .badge {{ display: inline-block; font-size: 0.7rem; padding: 2px 7px; border-radius: 4px;
            margin: 2px 2px 4px 0; font-weight: 600; }}
  .badge-new-stock  {{ background: #f59e0b; color: #1c1917; }}
  .badge-new-concept {{ background: #fb923c; color: #1c1917; }}
  /* 概念股標籤 */
  .tag {{ display: inline-block; font-size: 0.72rem; background: #1e3a5f; color: #93c5fd;
          padding: 2px 7px; border-radius: 4px; margin: 2px; }}
  .tag-highlight {{ background: #78350f; color: #fcd34d; }}
  /* 新聞 */
  .news-block {{ margin-top: 6px; }}
  .news-item {{ font-size: 0.78rem; color: var(--muted); margin: 3px 0; line-height: 1.4; }}
  .news-item a {{ color: #7dd3fc; text-decoration: none; }}
  .news-item a:hover {{ text-decoration: underline; }}
  .news-src {{ display: inline-block; font-size: 0.68rem; background: #1e3a5f; color: #93c5fd;
               padding: 1px 5px; border-radius: 3px; margin-right: 4px; }}
  .news-empty {{ font-size: 0.75rem; color: #475569; margin-top: 4px; }}
  /* 圖例 */
  .legend {{ display: flex; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; font-size: 0.82rem; }}
  .legend-item {{ display: flex; align-items: center; gap: 6px; }}
  .legend-dot {{ width: 14px; height: 14px; border-radius: 3px; }}
  @media (max-width: 768px) {{ body {{ padding: 12px; }} .chart-wrap {{ height: 220px; }} }}
</style>
</head>
<body>

<h1>📊 台股每日成交金額前30名</h1>
<div class="subtitle">資料日期：{report_date}　資料來源：台灣證交所 ＋ 鉅亨網 ＋ Yahoo股市</div>

<div class="stats">
  <div class="stat-card">
    <div class="stat-label">前30名合計成交金額</div>
    <div class="stat-value">{total_amt:.0f} 億</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">今日新進榜個股</div>
    <div class="stat-value">{sum(1 for s in stocks if s['code'] not in prev_codes and prev_codes)} 檔</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">今日新出現概念股</div>
    <div class="stat-value">{len(new_concepts)} 個</div>
  </div>
</div>

<div class="date-nav">
  <span style="color:var(--muted);font-size:.82rem;align-self:center;">歷史日期：</span>
  {nav_links}
  <a href="index.html" class="nav-date">📋 全部</a>
</div>

<div class="legend">
  <div class="legend-item"><div class="legend-dot" style="background:#3b82f6"></div>一般個股</div>
  <div class="legend-item"><div class="legend-dot" style="background:#f59e0b"></div>🟡 今日新進榜</div>
  <div class="legend-item"><div class="legend-dot" style="background:#fb923c"></div>🟠 新概念族群</div>
</div>

<div class="chart-card">
  <h2>成交金額（億元）— 前30名分布</h2>
  <div class="chart-wrap">
    <canvas id="barChart"></canvas>
  </div>
</div>

<div class="table-wrap">
  <table>
    <thead>
      <tr>
        <th>排名</th><th>代碼</th><th>名稱 / 新聞</th>
        <th>收盤價</th><th>成交張數</th><th>成交金額(億)</th>
        <th>所屬概念股</th><th>漲跌幅</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
</div>

<script>
const ctx = document.getElementById('barChart').getContext('2d');
new Chart(ctx, {{
  type: 'bar',
  data: {{
    labels: {bar_labels_js},
    datasets: [{{
      label: '成交金額（億）',
      data: {bar_amounts_js},
      backgroundColor: {bar_colors_js},
      borderRadius: 4,
    }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ display: false }},
      tooltip: {{
        callbacks: {{
          label: ctx => `成交金額：${{ctx.parsed.y.toFixed(2)}} 億`
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: '#94a3b8', font: {{ size: 10 }}, maxRotation: 45 }},
        grid: {{ color: '#1e293b' }}
      }},
      y: {{
        ticks: {{ color: '#94a3b8', callback: v => v + '億' }},
        grid: {{ color: '#1e293b' }}
      }}
    }}
  }}
}});
</script>

</body>
</html>"""

    return html


def generate_index_html(all_dates: list) -> str:
    """產生總覽首頁"""
    links = ""
    for d in all_dates:
        links += f'<a href="{d}.html" class="date-link">📅 {d}</a>\n'

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>台股每日成交金額報表 — 歷史總覽</title>
<style>
  body {{ background:#0f172a; color:#e2e8f0; font-family:-apple-system,"Noto Sans TC",sans-serif;
          padding:32px; max-width:700px; margin:auto; }}
  h1 {{ font-size:1.5rem; margin-bottom:8px; }}
  p {{ color:#94a3b8; margin-bottom:24px; font-size:.9rem; }}
  .date-link {{ display:block; background:#1e293b; color:#7dd3fc; padding:12px 18px;
                border-radius:8px; text-decoration:none; margin-bottom:8px; font-size:.95rem;
                transition:background .2s; }}
  .date-link:hover {{ background:#1e3a5f; }}
</style>
</head>
<body>
<h1>📊 台股每日成交金額前30名 — 歷史總覽</h1>
<p>共 {len(all_dates)} 份報表，點選日期查看當日詳細報表</p>
{links}
</body>
</html>"""


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

    print(f"[{report_date}] 開始抓取台股成交金額前30名...")

    # 1. 抓取今日排行
    stocks = fetch_twse_value30(twse_date)
    if not stocks:
        print("[ERROR] 無法取得今日資料，可能今日休市或資料尚未更新")
        sys.exit(1)
    print(f"  ✓ 取得 {len(stocks)} 筆資料")

    # 2. 抓新聞（每檔間隔 0.5 秒，避免被擋）
    print("  抓取個股新聞...")
    for s in stocks:
        s["news"] = fetch_all_news(s["code"], s["name"])
        time.sleep(0.5)
        print(f"    {s['code']} {s['name']}: {len(s['news'])} 則新聞")

    # 3. 讀昨日資料
    prev_data = load_previous_data(data_dir)
    print(f"  ✓ 前一日資料：{len(prev_data)} 檔")

    # 4. 儲存今日 JSON
    save_data = {
        "date":   report_date,
        "stocks": [{k: list(v) if isinstance(v, set) else v
                    for k, v in s.items() if k != "news"}
                   for s in stocks]
    }
    with open(data_dir / f"{report_date}.json", "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    # 5. 產生 HTML 報表
    all_dates = sorted(
        [f.stem for f in reports_dir.glob("????-??-??.html")],
        reverse=True
    )
    if report_date not in all_dates:
        all_dates = [report_date] + all_dates

    html = generate_html(stocks, prev_data, report_date, all_dates)
    report_path = reports_dir / f"{report_date}.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    # 6. 更新首頁
    index_html = generate_index_html(all_dates)
    with open(reports_dir / "index.html", "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"  ✓ 報表已產生：reports/{report_date}.html")
    print("完成！")


if __name__ == "__main__":
    main()
