"""PuLP を使った送料込み最安購入プランの最適化ソルバー"""

import json

from pulp import (
    PULP_CBC_CMD,
    LpBinary,
    LpMinimize,
    LpProblem,
    LpVariable,
    lpSum,
    value,
)


def load_shipping_rules(path: str = "shops.json") -> dict:
    with open(path) as f:
        return json.load(f)


def get_shipping(shop: str, rules: dict) -> dict:
    """ショップの送料ルールを取得する"""
    return rules.get(shop, rules["_default"])


def solve(
    price_data: dict[str, list[dict]],
    shipping_rules: dict,
) -> dict:
    """送料込みの最安購入プランを計算する

    Args:
        price_data: {カード名: [{shop, price, ...}, ...]}
        shipping_rules: {ショップ名: {shipping, free_threshold}}

    Returns:
        {
            "status": "Optimal" | ...,
            "total_cost": int,
            "card_cost": int,
            "shipping_cost": int,
            "plan": {ショップ名: [{card, price, set, ...}, ...]},
            "shop_details": {ショップ名: {subtotal, shipping, total}},
        }
    """
    prob = LpProblem("MTG_Optimizer", LpMinimize)

    # 全ショップを収集
    all_shops = set()
    for offers in price_data.values():
        for o in offers:
            all_shops.add(o["shop"])
    all_shops = sorted(all_shops)

    # --- 変数 ---
    # x[card][i]: カード card の i 番目の offer を選ぶか
    x = {}
    for card, offers in price_data.items():
        x[card] = {}
        for i in range(len(offers)):
            x[card][i] = LpVariable(f"x_{card}_{i}", cat=LpBinary)

    # y[shop]: ショップ shop を利用するか
    y = {shop: LpVariable(f"y_{shop}", cat=LpBinary) for shop in all_shops}

    # z[shop]: ショップ shop で送料無料条件を「満たさない」か (1=送料あり)
    z = {shop: LpVariable(f"z_{shop}", cat=LpBinary) for shop in all_shops}

    # --- 目的関数 ---
    # カード代 + 送料
    card_cost = lpSum(
        offers[i]["price"] * x[card][i]
        for card, offers in price_data.items()
        for i in range(len(offers))
    )

    shipping_cost = lpSum(
        get_shipping(shop, shipping_rules)["shipping"] * z[shop] for shop in all_shops
    )

    prob += card_cost + shipping_cost

    # --- 制約 ---
    # 各カードは必ず 1 つの offer から購入する
    for card, offers in price_data.items():
        prob += lpSum(x[card][i] for i in range(len(offers))) == 1

    # ショップ利用フラグとの連携
    for card, offers in price_data.items():
        for i, offer in enumerate(offers):
            prob += x[card][i] <= y[offer["shop"]]

    # 送料無料判定: free_threshold がある場合
    # subtotal >= free_threshold なら z=0 (送料無料)
    # そうでなければ z=1 (送料あり)
    # z >= y - subtotal / free_threshold (近似)
    BIG_M = 1_000_000
    for shop in all_shops:
        rule = get_shipping(shop, shipping_rules)
        threshold = rule.get("free_threshold")

        # ショップを使わないなら送料なし
        prob += z[shop] <= y[shop]

        if threshold:
            # subtotal: このショップでの購入合計
            subtotal = lpSum(
                offers[i]["price"] * x[card][i]
                for card, offers in price_data.items()
                for i, o in enumerate(offers)
                if o["shop"] == shop
            )
            # subtotal < threshold なら z=1 (送料あり)
            # subtotal >= threshold なら z=0 (送料無料) も許される
            # BIG_M * z >= threshold - subtotal を使う
            prob += BIG_M * z[shop] >= threshold - subtotal
            # subtotal < threshold のとき z=1 を強制するため:
            # z >= 1 - subtotal / threshold (不要、上の制約で十分)
        else:
            # free_threshold なし = 使うなら必ず送料がかかる
            prob += z[shop] >= y[shop]

    # --- 求解 ---
    prob.solve(PULP_CBC_CMD(msg=0))

    # --- 結果の整理 ---
    plan = {}
    shop_subtotals = {}
    shop_urls = {}
    for card, offers in price_data.items():
        for i, offer in enumerate(offers):
            if value(x[card][i]) and value(x[card][i]) > 0.5:
                shop = offer["shop"]
                if shop not in plan:
                    plan[shop] = []
                    shop_subtotals[shop] = 0
                if shop not in shop_urls:
                    rule = shipping_rules.get(shop, {})
                    shop_urls[shop] = rule.get("url")
                plan[shop].append(
                    {
                        "card": card,
                        "price": offer["price"],
                        "set": offer["set"],
                        "condition": offer["condition"],
                    }
                )
                shop_subtotals[shop] += offer["price"]

    shop_details = {}
    total_card = 0
    total_shipping = 0
    for shop, items in plan.items():
        subtotal = shop_subtotals[shop]
        rule = get_shipping(shop, shipping_rules)
        threshold = rule.get("free_threshold")
        shipping = rule["shipping"] if (not threshold or subtotal < threshold) else 0
        shop_details[shop] = {
            "subtotal": subtotal,
            "shipping": shipping,
            "total": subtotal + shipping,
        }
        total_card += subtotal
        total_shipping += shipping

    return {
        "status": prob.status,
        "total_cost": total_card + total_shipping,
        "card_cost": total_card,
        "shipping_cost": total_shipping,
        "plan": plan,
        "shop_details": shop_details,
        "shop_urls": shop_urls,
    }
