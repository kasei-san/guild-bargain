"""Claude CLI で最適解の説明・代替案・レコメンドを生成する"""

import json
import subprocess


def generate_advice(
    card_names: list[str],
    price_data: dict[str, list[dict]],
    solution: dict,
    shipping_rules: dict,
) -> str:
    """最適解をもとに購入アドバイスを生成する"""

    # 価格データを上位5件ずつに絞る（トークン節約）
    trimmed = {}
    for card, offers in price_data.items():
        sorted_offers = sorted(offers, key=lambda o: o["price"])
        trimmed[card] = sorted_offers[:5]

    prompt = f"""以下のMTGカードの最適購入プランを分かりやすく説明してください。

# 最適解（PuLPソルバーによる厳密計算結果）
- 合計金額: {solution["total_cost"]}円（カード代: {solution["card_cost"]}円 + 送料: {solution["shipping_cost"]}円）

## 購入プラン
{json.dumps(solution["plan"], ensure_ascii=False, indent=2)}

## ショップ別明細
{json.dumps(solution["shop_details"], ensure_ascii=False, indent=2)}

# 各カードの価格情報（上位5件、参考用）
{json.dumps(trimmed, ensure_ascii=False, indent=2)}

# 送料ルール
{json.dumps(shipping_rules, ensure_ascii=False, indent=2)}

# 出力してほしい内容
1. **購入プラン**: 最適解を分かりやすく整理して表示。各ショップで何を買うか、小計・送料・合計を見やすく。
2. **代替プラン**: 少し高くなるが店数が少ない案など、トレードオフがあれば1〜2案提示。なければ省略。
3. **コスト削減レコメンド**: 「このカードを諦めれば X 円安くなる」「別のショップにまとめれば送料を節約できる」等のヒント。なければ省略。

簡潔に、実用的な情報だけ出力してください。"""

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI エラー: {result.stderr}")
    return result.stdout
