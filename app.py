"""Streamlit Web UI for MTG Card Purchase Optimizer"""

import streamlit as st
import pandas as pd

from scraper import fetch_all_cards
from solver import load_shipping_rules, solve
from normalizer import normalize_card_names
from advisor import generate_advice

st.set_page_config(page_title="MTG 最安購入オプティマイザー", layout="wide")
st.title("MTG 最安購入オプティマイザー")

# --- サイドバー ---
with st.sidebar:
    st.header("オプション")
    use_normalizer = st.checkbox("カード名を正規化する (Claude CLI)", value=False)
    use_advisor = st.checkbox("購入アドバイスを生成する (Claude CLI)", value=False)
    if use_normalizer or use_advisor:
        st.caption("Claude CLI の呼び出しには時間がかかります")

# --- 入力 ---
card_input = st.text_area(
    "カード名を1行1枚で入力してください",
    height=200,
    placeholder="例:\n稲妻\n対抗呪文\nSwords to Plowshares",
)

if st.button("最適化", type="primary", disabled=not card_input.strip()):
    card_names = [line.strip() for line in card_input.strip().splitlines() if line.strip()]

    if not card_names:
        st.error("カード名を入力してください")
        st.stop()

    shipping_rules = load_shipping_rules()

    # Step 1: 正規化
    if use_normalizer:
        with st.status("カード名を正規化中...", expanded=True) as status:
            try:
                normalized = normalize_card_names(card_names)
                changes = [
                    (orig, norm)
                    for orig, norm in zip(card_names, normalized)
                    if orig != norm
                ]
                if changes:
                    st.write("修正されたカード名:")
                    for orig, norm in changes:
                        st.write(f"  {orig} → {norm}")
                    card_names = normalized
                else:
                    st.write("修正なし")

                unknown = [n for n in card_names if n.startswith("UNKNOWN:")]
                if unknown:
                    st.warning(f"特定できなかったカード: {', '.join(unknown)}")
                    card_names = [n for n in card_names if not n.startswith("UNKNOWN:")]

                status.update(label="正規化完了", state="complete")
            except Exception as e:
                status.update(label="正規化エラー", state="error")
                st.error(f"正規化エラー: {e}")
                st.stop()

    # Step 2: スクレイピング
    with st.status(f"価格情報を取得中 (全{len(card_names)}枚)...", expanded=True) as status:
        progress = st.progress(0)
        price_data = {}
        for i, name in enumerate(card_names):
            st.write(f"[{i + 1}/{len(card_names)}] {name}")
            try:
                from scraper import fetch_card_prices
                import time

                prices = fetch_card_prices(name)
                price_data[name] = prices
                st.write(f"  → {len(prices)} 件")
            except Exception as e:
                st.write(f"  → エラー: {e}")
                price_data[name] = []

            progress.progress((i + 1) / len(card_names))
            if i < len(card_names) - 1:
                time.sleep(1.5)

        status.update(label="価格情報の取得完了", state="complete")

    missing = [name for name, offers in price_data.items() if not offers]
    if missing:
        st.warning(f"価格情報が見つからなかったカード: {', '.join(missing)}")
        price_data = {k: v for k, v in price_data.items() if v}

    if not price_data:
        st.error("価格情報が1件も取得できませんでした。カード名を確認してください。")
        st.stop()

    # Step 3: 最適化
    with st.status("最適化計算中...", expanded=False) as status:
        result = solve(price_data, shipping_rules)
        if result["status"] != 1:
            st.error(f"最適解が見つかりませんでした (status: {result['status']})")
            st.stop()
        status.update(label="最適化完了", state="complete")

    # --- 結果表示 ---
    st.divider()
    st.header("最適購入プラン")

    col1, col2, col3 = st.columns(3)
    col1.metric("合計金額", f"¥{result['total_cost']:,}")
    col2.metric("カード代", f"¥{result['card_cost']:,}")
    col3.metric("送料", f"¥{result['shipping_cost']:,}")

    st.subheader(f"利用ショップ: {len(result['plan'])}店")

    for shop, items in result["plan"].items():
        details = result["shop_details"][shop]
        with st.expander(
            f"{shop}  (小計: ¥{details['subtotal']:,} + 送料: ¥{details['shipping']:,} = ¥{details['total']:,})",
            expanded=True,
        ):
            rows = [
                {
                    "カード名": item["card"],
                    "価格": f"¥{item['price']:,}",
                    "セット": item["set"],
                    "状態": item["condition"],
                }
                for item in items
            ]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.caption(
        "※ 価格データは Wisdom Guild 経由の情報です。"
        "実際の在庫・価格はショップ側で変動している場合があります。"
        "購入前に各ショップの販売ページで最新情報を確認してください。"
    )

    # Step 4: アドバイス
    if use_advisor:
        with st.status("アドバイスを生成中...", expanded=True) as status:
            try:
                advice = generate_advice(card_names, price_data, result, shipping_rules)
                status.update(label="アドバイス生成完了", state="complete")
            except Exception as e:
                st.error(f"Claude API エラー: {e}")
                advice = None

        if advice:
            st.subheader("購入アドバイス")
            st.markdown(advice)
