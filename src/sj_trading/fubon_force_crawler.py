"""
富邦證券主力/投信買超排行爬蟲
=============================
URL 模式:
  https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm  → 上市主力買超2日排行
  https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_DD.djhtm    → 上市投信買超1日排行

方法: requests + BeautifulSoup，完全不用 Shioaji API

富邦證券 URL 參數模式：
  zg_F_* = 主力買超排行 (F=主力)
    zg_F_0_0  → 上市主力買超1日   (0=上市, 0=1日)
    zg_F_0_2  → 上市主力買超2日
    zg_F_0_3  → 上市主力買超3日
    zg_F_0_4  → 上市主力買超4日
    zg_F_1_0  → 上櫃主力買超1日    (1=上櫃)
  
  zg_DD* = 投信買超排行
    zg_DD.djhtm   → 上市投信買超1日 (預設)
    zg_DD.djhtm?M=003 → 上市投信買超3日
    zg_DD.djhtm?M=101 → 上櫃投信買超1日
  
  zg_DE = 投信賣超排行
"""

import requests
import re
import json
import sys
from bs4 import BeautifulSoup

# 主力買超2日排行 URL (你指定的)
MAIN_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm"

# 富邦主力買超2日排行預設 URL
FORCE_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_F_0_2.djhtm"

# 富邦投信買超1日排行預設 URL
TRUST_URL = "https://fubon-ebrokerdj.fbs.com.tw/z/zg/zg_DD.djhtm"

FULL_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
    "Referer": "https://fubon-ebrokerdj.fbs.com.tw/",
}


def fubon_crawler(url=FORCE_URL, top=20):
    """
    從富邦證券爬取買超排行 (通用，支援主力/投信)。

    Parameters
    ----------
    url : str
        目標網址 (預設主力買超2日)
    top : int
        取前 N 名 (預設 20)

    Returns
    -------
    list[dict]
        [{"rank":1, "code":"3231", "name":"緯創", "buy":66057, "sell":18982, "net":47074}, ...]
    """
    resp = requests.get(url, headers=FULL_HEADERS, timeout=30)
    resp.encoding = "big5"
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    table = soup.find("table", id="oMainTable")
    if not table:
        raise RuntimeError("找不到主表格 oMainTable，可能網站改版了")

    results = []
    rows = table.find_all("tr")

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 8:
            continue

        rank_text = cells[0].get_text(strip=True)
        if not rank_text.isdigit():
            continue  # 跳過表頭列

        rank = int(rank_text)
        if rank > top:
            break

        # 股票名稱: "3231 緯創" 或 "00403A主動統一升級50"
        name_raw = cells[1].get_text(strip=True)
        m = re.match(r"(\d{4,6}[A-Za-z]?)\s*(.*)", name_raw)
        if m:
            code = m.group(1)
            name = m.group(2).strip()
        else:
            code = name_raw
            name = ""

        buy = int(cells[5].get_text(strip=True).replace(",", ""))
        sell = int(cells[6].get_text(strip=True).replace(",", ""))
        net = int(cells[7].get_text(strip=True).replace(",", ""))

        results.append({
            "rank": rank,
            "code": code,
            "name": name,
            "buy": buy,
            "sell": sell,
            "net": net,
        })

    return results


def fetch_force_top_2d(top=20):
    """快捷方法: 上市主力買超2日排行"""
    return fubon_crawler(url=FORCE_URL, top=top)


def fetch_trust_top_1d(top=20):
    """快捷方法: 上市投信買超1日排行"""
    return fubon_crawler(url=TRUST_URL, top=top)


def print_table(data, title=""):
    """列印表格"""
    if title:
        print(f"\n{'=' * 50}")
        print(f"  {title}")
        print(f"{'=' * 50}")
    print(f"{'#':<3} {'代碼':<8} {'名稱':<18} {'買進':<10} {'賣出':<10} {'買賣超':<10}")
    print("-" * 62)
    for it in data:
        print(f"{it['rank']:<3} {it['code']:<8} {it['name']:<18} "
              f"{it['buy']:<10,} {it['sell']:<10,} {it['net']:<10,}")
    tb = sum(d["buy"] for d in data)
    ts = sum(d["sell"] for d in data)
    tn = sum(d["net"] for d in data)
    print("-" * 62)
    print(f"{'合計':<12} {tb:<10,} {ts:<10,} {tn:<10,}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="富邦證券買超排行爬蟲")
    parser.add_argument("--top", type=int, default=20, help="取前N名 (預設20)")
    parser.add_argument("--json", action="store_true", help="輸出JSON")
    parser.add_argument(
        "--mode", choices=["force", "trust", "both"], default="both",
        help="force=主力買超2日, trust=投信買超1日, both=兩個都爬 (預設both)"
    )
    parser.add_argument("--url", help="自訂URL (mode=force/trust時有效)")
    args = parser.parse_args()

    if args.json:
        # JSON 模式只爬單一 mode
        if args.mode == "force":
            url = args.url or FORCE_URL
            data = fubon_crawler(url=url, top=args.top)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        elif args.mode == "trust":
            url = args.url or TRUST_URL
            data = fubon_crawler(url=url, top=args.top)
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            force = fubon_crawler(url=FORCE_URL, top=args.top)
            trust = fubon_crawler(url=TRUST_URL, top=args.top)
            print(json.dumps({"force": force, "trust": trust}, ensure_ascii=False, indent=2))
        return

    # 表格模式
    if args.mode in ("force", "both"):
        url = args.url or FORCE_URL
        print(f"📡 上市主力買超2日排行 (TOP {args.top})")
        force_data = fubon_crawler(url=url, top=args.top)
        print_table(force_data)

    if args.mode in ("trust", "both"):
        url = args.url or TRUST_URL
        print(f"\n📡 上市投信買超1日排行 (TOP {args.top})")
        trust_data = fubon_crawler(url=url, top=args.top)
        print_table(trust_data)


if __name__ == "__main__":
    main()
