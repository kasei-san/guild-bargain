"""MTG カード最安購入オプティマイザー"""

import argparse
import json
import sys

from normalizer import normalize_card_names
from scraper import fetch_all_cards
from solver import load_shipping_rules, solve
from advisor import generate_advice


def load_card_list(path: str) -> list[str]:
    with open(path) as f:
        return [line.strip() for line in f if line.strip()]


def main():
    parser = argparse.ArgumentParser(description="MTG カード最安購入オプティマイザー")
    parser.add_argument(
        "-c", "--cards", default="cards.txt", help="カードリストファイル (default: cards.txt)"
    )
    parser.add_argument(
        "-s", "--shops", default="shops.json", help="送料ルールファイル (default: shops.json)"
    )
    parser.add_argument(
        "--no-advice", action="store_true", help="Claude API による説明生成をスキップ"
    )
    args = parser.parse_args()

    # Step 0: 入力読み込み
    card_names = load_card_list(args.cards)
    shipping_rules = load_shipping_rules(args.shops)
    print(f"カード {len(card_names)} 枚の最安購入プランを計算します\n")

    # Step 1: カード名の正規化
    if not args.no_advice:
        print("== Step 1: カード名を正規化中 ==")
        try:
            normalized = normalize_card_names(card_names)
            changes = []
            for orig, norm in zip(card_names, normalized):
                if orig != norm:
                    changes.append((orig, norm))
            if changes:
                print("  以下のカード名を修正しました:")
                for orig, norm in changes:
                    print(f"    {orig} → {norm}")
                card_names = normalized
            else:
                print("  修正なし")
            # UNKNOWN チェック
            unknown = [n for n in card_names if n.startswith("UNKNOWN:")]
            if unknown:
                print(f"\n⚠ 以下のカードは特定できませんでした:")
                for u in unknown:
                    print(f"  - {u}")
                card_names = [n for n in card_names if not n.startswith("UNKNOWN:")]
        except Exception as e:
            print(f"  正規化スキップ（エラー: {e}）")
        print()

    # Step 2: スクレイピング
    print("== Step 2: 価格情報を取得中 ==")
    price_data = fetch_all_cards(card_names)

    # 取得できなかったカードを警告
    missing = [name for name, offers in price_data.items() if not offers]
    if missing:
        print(f"\n⚠ 以下のカードは価格情報が見つかりませんでした:")
        for name in missing:
            print(f"  - {name}")
        # 取得できたカードだけで最適化
        price_data = {k: v for k, v in price_data.items() if v}

    if not price_data:
        print("\n価格情報が1件も取得できませんでした。カード名を確認してください。")
        sys.exit(1)

    # Step 3: 最適化
    print("\n== Step 3: 最適化計算中 ==")
    result = solve(price_data, shipping_rules)

    if result["status"] != 1:  # 1 = Optimal
        print(f"\n最適解が見つかりませんでした (status: {result['status']})")
        sys.exit(1)

    # 結果表示（ソルバー出力）
    print(f"\n{'='*50}")
    print(f"最適購入プラン")
    print(f"{'='*50}")
    print(f"合計: {result['total_cost']}円 (カード代: {result['card_cost']}円 + 送料: {result['shipping_cost']}円)")
    print(f"利用ショップ数: {len(result['plan'])}店")
    print()

    for shop, items in result["plan"].items():
        details = result["shop_details"][shop]
        print(f"■ {shop} (小計: {details['subtotal']}円 + 送料: {details['shipping']}円 = {details['total']}円)")
        for item in items:
            print(f"  - {item['card']}  {item['price']}円  ({item['set']}, {item['condition']})")
        print()

    # Step 4: Claude CLI で説明・レコメンド
    if not args.no_advice:
        print("== Step 4: アドバイスを生成中 ==\n")
        try:
            advice = generate_advice(card_names, price_data, result, shipping_rules)
            print(advice)
        except Exception as e:
            print(f"Claude API エラー: {e}")
            print("--no-advice オプションで API 呼び出しをスキップできます。")


if __name__ == "__main__":
    main()
