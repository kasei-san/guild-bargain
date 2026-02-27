"""Streamlit Web UI for MTG Card Purchase Optimizer"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd

from cache import cleanup_expired
from scraper import fetch_all_cards
from solver import load_shipping_rules, solve
from normalizer import _normalize_batch, BATCH_SIZE
from advisor import generate_advice

cleanup_expired()

st.set_page_config(page_title="MTG 最安購入オプティマイザー", layout="wide")
st.title("MTG 最安購入オプティマイザー")


# --- session_state 初期化 ---
if "card_default" not in st.session_state:
    st.session_state.card_default = ""
if "processing" not in st.session_state:
    st.session_state.processing = False
if "normalize_done" not in st.session_state:
    st.session_state.normalize_done = False
if "run_normalize" not in st.session_state:
    st.session_state.run_normalize = False
if "run_optimize" not in st.session_state:
    st.session_state.run_optimize = False
if "result" not in st.session_state:
    st.session_state.result = None
if "price_data" not in st.session_state:
    st.session_state.price_data = None
if "card_names_for_advice" not in st.session_state:
    st.session_state.card_names_for_advice = None
if "shipping_rules" not in st.session_state:
    st.session_state.shipping_rules = None
if "scroll_to_result" not in st.session_state:
    st.session_state.scroll_to_result = False
if "run_advice" not in st.session_state:
    st.session_state.run_advice = False
if "advice" not in st.session_state:
    st.session_state.advice = None

# --- 正規化完了通知 ---
if st.session_state.normalize_done:
    st.toast("カード名の正規化が完了しました", icon="✅")
    st.session_state.normalize_done = False

# --- 入力 ---
card_input = st.text_area(
    "カード名を1行1枚で入力してください",
    value=st.session_state.card_default,
    height=200,
    placeholder="例:\n稲妻\n対抗呪文\nSwords to Plowshares",
)

# --- ボタン横並び ---
col_opt, col_norm = st.columns(2)

with col_opt:
    buttons_disabled = st.session_state.processing or not card_input.strip()
    optimize_clicked = st.button("最安購入チェック!!", type="primary", disabled=buttons_disabled)

with col_norm:
    normalize_clicked = st.button("カード名正規化", disabled=buttons_disabled)

# --- ボタン押下時: フラグを立ててrerunし、UIを更新してから処理開始 ---
if normalize_clicked:
    st.session_state.processing = True
    st.session_state.run_normalize = True
    st.rerun()

if optimize_clicked:
    st.session_state.processing = True
    st.session_state.run_optimize = True
    st.rerun()

# --- 正規化処理 ---
if st.session_state.run_normalize:
    st.session_state.run_normalize = False
    card_names = [line.strip() for line in card_input.strip().splitlines() if line.strip()]
    if not card_names:
        st.error("カード名を入力してください")
        st.session_state.processing = False
        st.stop()

    total = len(card_names)
    with st.status(f"カード名を正規化中... (0/{total})", expanded=True) as status:
        try:
            normalized = []
            for i in range(0, total, BATCH_SIZE):
                batch = card_names[i : i + BATCH_SIZE]
                done = min(i + BATCH_SIZE, total)
                status.update(label=f"カード名を正規化中... ({done}/{total})")
                st.write(f"[{done}/{total}] {', '.join(batch)}")
                normalized.extend(_normalize_batch(batch))

            changes = [
                (orig, norm)
                for orig, norm in zip(card_names, normalized)
                if orig != norm
            ]
            if changes:
                st.write("修正されたカード名:")
                for orig, norm in changes:
                    st.write(f"  {orig} → {norm}")
            else:
                st.write("修正なし")

            unknown = [n for n in normalized if n.startswith("UNKNOWN:")]
            if unknown:
                st.warning(f"特定できなかったカード: {', '.join(unknown)}")

            # UNKNOWNを除外してテキストエリアを書き換え
            valid = [n for n in normalized if not n.startswith("UNKNOWN:")]
            st.session_state.card_default = "\n".join(valid)
            status.update(label="正規化完了", state="complete")
        except Exception as e:
            status.update(label="正規化エラー", state="error")
            st.error(f"正規化エラー: {e}")
            st.session_state.processing = False
            st.stop()

    st.session_state.processing = False
    st.session_state.normalize_done = True
    st.rerun()

# --- 最適化処理 ---
if st.session_state.run_optimize:
    st.session_state.run_optimize = False
    card_names = [line.strip() for line in card_input.strip().splitlines() if line.strip()]

    if not card_names:
        st.error("カード名を入力してください")
        st.session_state.processing = False
        st.stop()

    shipping_rules = load_shipping_rules()

    # Step 1: スクレイピング
    with st.status(f"価格情報を取得中 (全{len(card_names)}枚)...", expanded=True) as status:
        progress = st.progress(0)
        price_data = {}
        for i, name in enumerate(card_names):
            st.write(f"[{i + 1}/{len(card_names)}] {name}")
            try:
                from scraper import fetch_card_prices
                from cache import get_cached
                import time

                cached = get_cached(name) is not None
                prices = fetch_card_prices(name)
                price_data[name] = prices
                hit = "キャッシュヒット! → " if cached else ""
                st.write(f"  → {hit}{len(prices)} 件")
            except Exception as e:
                st.write(f"  → エラー: {e}")
                price_data[name] = []
                cached = False

            progress.progress((i + 1) / len(card_names))
            if i < len(card_names) - 1 and not cached:
                time.sleep(1.5)

        status.update(label="価格情報の取得完了", state="complete")

    missing = [name for name, offers in price_data.items() if not offers]
    if missing:
        st.warning(f"価格情報が見つからなかったカード: {', '.join(missing)}")
        price_data = {k: v for k, v in price_data.items() if v}

    if not price_data:
        st.error("価格情報が1件も取得できませんでした。カード名を確認してください。")
        st.stop()

    # Step 2: 最適化
    with st.status("最適化計算中...", expanded=False) as status:
        result = solve(price_data, shipping_rules)
        if result["status"] != 1:
            st.error(f"最適解が見つかりませんでした (status: {result['status']})")
            st.session_state.processing = False
            st.stop()
        status.update(label="最適化完了", state="complete")

    # session_stateに結果を保存（前回のアドバイスはクリア）
    st.session_state.advice = None
    st.session_state.result = result
    st.session_state.price_data = price_data
    st.session_state.card_names_for_advice = card_names
    st.session_state.shipping_rules = shipping_rules
    st.session_state.scroll_to_result = True
    st.session_state.processing = False

# --- 結果表示（session_stateから） ---
if st.session_state.result is not None:
    result = st.session_state.result

    st.divider()
    st.header("最適購入プラン", anchor="result")
    if st.session_state.scroll_to_result:
        st.session_state.scroll_to_result = False
        components.html(
            "<script>window.parent.document.getElementById('result').scrollIntoView({behavior:'smooth'})</script>",
            height=0,
        )

    col1, col2, col3 = st.columns(3)
    col1.metric("合計金額", f"¥{result['total_cost']:,}")
    col2.metric("カード代", f"¥{result['card_cost']:,}")
    col3.metric("送料", f"¥{result['shipping_cost']:,}")

    st.subheader(f"利用ショップ: {len(result['plan'])}店")

    for shop, items in result["plan"].items():
        details = result["shop_details"][shop]
        shop_url = result.get("shop_urls", {}).get(shop)
        shop_label = f"[{shop}]({shop_url})" if shop_url else shop
        with st.expander(
            f"{shop}  (小計: ¥{details['subtotal']:,} + 送料: ¥{details['shipping']:,} = ¥{details['total']:,})",
            expanded=True,
        ):
            st.markdown(f"### {shop_label}")
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

    # Step 3: アドバイスボタン
    if st.button("購入アドバイスを生成する (Claude CLI)", disabled=st.session_state.run_advice):
        st.session_state.run_advice = True
        st.rerun()

    # アドバイス表示（生成済みの場合）
    if st.session_state.advice:
        st.subheader("購入アドバイス")
        st.markdown(st.session_state.advice)

# --- アドバイス生成処理 ---
if st.session_state.run_advice:
    st.session_state.run_advice = False
    with st.status("アドバイスを生成中...", expanded=True) as status:
        try:
            advice = generate_advice(
                st.session_state.card_names_for_advice,
                st.session_state.price_data,
                st.session_state.result,
                st.session_state.shipping_rules,
            )
            st.session_state.advice = advice
            status.update(label="アドバイス生成完了", state="complete")
        except Exception as e:
            st.error(f"Claude API エラー: {e}")
    st.rerun()
