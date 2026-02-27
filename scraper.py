"""Wisdom Guild からカード価格情報をスクレイピングする"""

import re
import time
import urllib.parse

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://wonder.wisdom-guild.net/price/{}/?stock_gt=1"
HEADERS = {"User-Agent": "Mozilla/5.0"}
REQUEST_INTERVAL = 1.5  # 秒


def fetch_card_prices(card_name: str) -> list[dict]:
    """カード名から価格情報を取得する"""
    encoded = urllib.parse.quote(card_name, safe="")
    url = BASE_URL.format(encoded)
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return _parse_price_table(resp.text)


def _parse_price_table(html: str) -> list[dict]:
    """HTML から価格テーブルをパースする"""
    soup = BeautifulSoup(html, "html.parser")
    tables = soup.find_all("table")

    # 価格テーブルはヘッダーに「ショップ」「価格」を含むテーブル
    price_table = None
    for t in tables:
        headers = [th.get_text(strip=True) for th in t.find_all("th")]
        if "ショップ" in headers and "価格" in headers:
            price_table = t
            break

    if price_table is None:
        return []

    results = []
    rows = price_table.find_all("tr")[1:]  # ヘッダー行をスキップ
    for row in rows:
        cells = row.find_all("td")
        if len(cells) < 7:
            continue

        shop = cells[0].get_text(strip=True)
        price_text = cells[1].get_text(strip=True)
        card_set = cells[2].get_text(strip=True)
        language = cells[3].get_text(strip=True)
        stock_text = cells[4].get_text(strip=True)
        condition = cells[6].get_text(strip=True)

        # 価格をパース（"900円" → 900, "1,200円" → 1200）
        price_match = re.search(r"[\d,]+", price_text)
        if not price_match:
            continue
        price = int(price_match.group().replace(",", ""))

        # 在庫をパース（"1 枚" → 1）
        stock_match = re.search(r"\d+", stock_text)
        stock = int(stock_match.group()) if stock_match else 0

        results.append(
            {
                "shop": shop,
                "price": price,
                "set": card_set,
                "language": language,
                "stock": stock,
                "condition": condition or "不明",
            }
        )

    return results


def fetch_all_cards(card_names: list[str]) -> dict[str, list[dict]]:
    """複数カードの価格情報をまとめて取得する"""
    all_prices = {}
    for i, name in enumerate(card_names):
        print(f"  [{i + 1}/{len(card_names)}] {name} ...", end=" ", flush=True)
        try:
            prices = fetch_card_prices(name)
            all_prices[name] = prices
            print(f"{len(prices)} 件")
        except Exception as e:
            print(f"エラー: {e}")
            all_prices[name] = []

        if i < len(card_names) - 1:
            time.sleep(REQUEST_INTERVAL)

    return all_prices
