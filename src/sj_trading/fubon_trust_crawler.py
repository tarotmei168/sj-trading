"""
富邦證券投信買超排行爬蟲
=======================
URL: https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_DD.djhtm
方法: requests + BeautifulSoup，完全不用 API
輸出: 前 20 檔股票代碼 + 名稱

可選天數:
  - '001': 上市投信買超1日排行 (預設)
  - '002': 上市投信買超2日排行
  - '003': 上市投信買超3日排行
  - '004': 上市投信買超4日排行
  - '005': 上市投信買超5日排行
  - '010': 上市投信買超10日排行
  - '020': 上市投信買超20日排行
  - '030': 上市投信買超30日排行
  
  - '101': 上櫃投信買超1日排行 (OTC)
  - '0-1': 上市投信買超1週以來
  - '1-1': 上櫃投信買超1週以來

使用方式:
  python fubon_trust_crawler.py              # 預設上市1日
  python fubon_trust_crawler.py --days 005    # 上市5日
  python fubon_trust_crawler.py --days 101    # 上櫃1日
  python fubon_trust_crawler.py --top 10      # 只取前10檔
"""

import requests
import re
import argparse
import json
import sys
from bs4 import BeautifulSoup

BASE_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_DD.djhtm"

# 天數代號對照
DAY_LABELS = {
    "001": "上市投信買超1日",
    "002": "上市投信買超2日",
    "003": "上市投信買超3日",
    "004": "上市投信買超4日",
    "005": "上市投信買超5日",
    "010": "上市投信買超10日",
    "020": "上市投信買超20日",
    "030": "上市投信買超30日",
    "101": "上櫃投信買超1日",
    "102": "上櫃投信買超2日",
    "103": "上櫃投信買超3日",
    "104": "上櫃投信買超4日",
    "105": "上櫃投信買超5日",
    "110": "上櫃投信買超10日",
    "120": "上櫃投信買超20日",
    "130": "上櫃投信買超30日",
    "0-1": "上市投信買超1週以來",
    "1-1": "上櫃投信買超1週以來",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://fubon-ebrokerdj.fbs.com.tw/",
}


def fetch_trust_buy(days="001", top=20):
    """
    從富邦證券爬取投信買超排行。

    Parameters
    ----------
    days : str
        天數代號 (預設 '001' = 上市1日)
    top : int
        取前 N 名 (預設 20)

    Returns
    -------
    list[dict]
        [{"rank": 1, "code": "2880", "name": "華南金", "buy": 10951, "sell": 748, "net": 10202}, ...]
    """
    url = f"{BASE_URL}?M={days}"
    
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.encoding = "big5"  # 富邦站用 big5 編碼
    resp.raise_for_status()
    
    soup = BeautifulSoup(resp.text, "lxml")
    
    # 找到主表格
    table = soup.find("table", id="oMainTable")
    if not table:
        table = soup.find("table", class_="t01")
    if not table:
        # fallback: 找所有 table，取最大的
        tables = soup.find_all("table", class_="t01")
        if tables:
            table = tables[0]
    
    if not table:
        raise RuntimeError("找不到表格資料，可能是網頁結構有變")
    
    rows = table.find_all("tr")
    
    results = []
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue
        
        rank_text = cells[0].get_text(strip=True)
        if not rank_text.isdigit():
            continue  # 跳過表頭
        
        rank = int(rank_text)
        if rank > top:
            break  # 只取前 N 名
        
        # 股票名稱: "2880  華南金" 或 "00922 國泰台灣領袖50"
        name_text = cells[1].get_text(strip=True)
        
        # 用 regex 解析股票代碼 + 名稱
        # 代碼是 4~6 位數字（含 ETF 代碼）
        m = re.match(r"(\d{4,6})\s+(.*)", name_text)
        if m:
            code = m.group(1)
            name = m.group(2).strip()
        else:
            code = name_text
            name = ""
        
        # 解析買進/賣出/買賣超張數 (去除逗號)
        buy_text = cells[5].get_text(strip=True)
        sell_text = cells[6].get_text(strip=True)
        net_text = cells[7].get_text(strip=True)
        
        buy = int(buy_text.replace(",", ""))
        sell = int(sell_text.replace(",", ""))
        net = int(net_text.replace(",", ""))
        
        results.append({
            "rank": rank,
            "code": code,
            "name": name,
            "buy": buy,
            "sell": sell,
            "net": net,
        })
    
    return results


def parse_args():
    parser = argparse.ArgumentParser(
        description="富邦證券投信買超排行爬蟲"
    )
    parser.add_argument(
        "--days", type=str, default="001",
        help="天數代號 (預設 001=上市1日)，例如: 002, 003, 005, 010, 101(上櫃1日)"
    )
    parser.add_argument(
        "--top", type=int, default=20,
        help="取前 N 名 (預設 20)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="輸出為 JSON 格式"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    
    label = DAY_LABELS.get(args.days, f"代號={args.days}")
    print(f"🦞 爬取: {label} (前{args.top}名)")
    print(f"    URL: {BASE_URL}?M={args.days}")
    print()
    
    try:
        data = fetch_trust_buy(days=args.days, top=args.top)
    except Exception as e:
        print(f"❌ 爬取失敗: {e}", file=sys.stderr)
        sys.exit(1)
    
    if not data:
        print("⚠️  沒有抓到任何資料")
        sys.exit(1)
    
    if args.json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return
    
    print(f"{'名次':<4} {'代碼':<7} {'名稱':<16} {'買進張數':<10} {'賣出張數':<10} {'買賣超':<10}")
    print("-" * 60)
    for item in data:
        print(f"{item['rank']:<4} {item['code']:<7} {item['name']:<16} "
              f"{item['buy']:<10,} {item['sell']:<10,} {item['net']:<10,}")
    
    # 彙總
    total_buy = sum(item["buy"] for item in data)
    total_sell = sum(item["sell"] for item in data)
    total_net = sum(item["net"] for item in data)
    print("-" * 60)
    print(f"{'合計':<12} {total_buy:<10,} {total_sell:<10,} {total_net:<10,}")


if __name__ == "__main__":
    main()
