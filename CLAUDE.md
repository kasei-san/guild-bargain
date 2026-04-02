# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## リポジトリ

https://github.com/kasei-san/guild-bargain

## プロジェクト概要

MTGカードの最安購入プランを提案するツール。Wisdom Guild から各ショップの価格をスクレイピングし、PuLP（ILPソルバー）で送料を含めた最適化計算を行い、最も安い買い方を提案する。CLIとStreamlit Web UIの両方で利用可能。

## コマンド

```bash
# セットアップ（Python 3.10+仮想環境 + 依存パッケージ）
./setup.sh

# Web UI起動
./run.sh

# CLI実行
python3 main.py                    # デフォルト（cards.txt使用）
python3 main.py -c mylist.txt      # カードリスト指定
python3 main.py -s custom.json     # 送料ルール指定
python3 main.py --no-advice        # Claude CLI呼び出しスキップ
```

テストフレームワークは未導入。

## アーキテクチャ

エントリポイント: `main.py`（CLI）、`app.py`（Streamlit Web UI）

4段階のパイプライン処理:

1. **normalizer.py** — Claude CLI(`claude -p`)をサブプロセスで呼び出し、カード名の表記揺れを正規化（10枚ずつバッチ処理、JSON配列で出力）
2. **scraper.py** — Wisdom Guildから価格データをスクレイピング（BeautifulSoup、最大2ページ、1.5秒間隔）
3. **solver.py** — PuLP CBCソルバーでILP最適化。BIG_M法で送料無料条件をモデル化し「カード代+送料」の合計を最小化
4. **advisor.py** — Claude CLI(`claude -p`)をサブプロセスで呼び出し、最適解のアドバイス生成（価格データは上位5件に絞ってトークン節約）

補助モジュール:
- **cache.py** — `.cache/prices/` にカード別JSONファイルでスクレイピング結果をキャッシュ（TTL 24時間）。起動時に `cleanup_expired()` で期限切れを削除

### 主要なデータ構造

パイプライン全体で共有される `price_data` の形式:
```python
{カード名: [{"shop", "price", "set", "language", "stock", "condition", "shop_url"}, ...]}
```

solver の出力 `result`:
```python
{"status", "total_cost", "card_cost", "shipping_cost", "plan": {shop: [items]}, "shop_details": {shop: {subtotal, shipping, total}}, "shop_urls": {shop: url}}
```

## 送料ルール（shops.json）

各ショップの`shipping`（基本送料）、`free_threshold`（送料無料条件、nullは無料なし）、`url`（ショップURL、Web UIでリンク表示に使用）を定義。未登録ショップは`_default`ルールが適用される。

## 外部依存

- **Claude CLI** (`claude -p`): normalizer.py と advisor.py がサブプロセスとして呼び出す。`--no-advice` オプションでスキップ可能
- **Wisdom Guild** (`wonder.wisdom-guild.net`): scraper.py のスクレイピング先。HTMLテーブル構造に依存しているため、サイト側の変更で壊れる可能性あり
