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

4段階のパイプライン処理:

1. **normalizer.py** — Claude CLI(`claude -p`)でカード名の表記揺れを正規化（JSON配列で出力）
2. **scraper.py** — Wisdom Guildから価格データをスクレイピング（BeautifulSoup、ページネーション対応、1.5秒間隔）
3. **solver.py** — PuLP CBCソルバーでILP最適化。BIG_M法で送料無料条件をモデル化し「カード代+送料」の合計を最小化
4. **advisor.py** — Claude CLIに最適解を渡してアドバイス生成（上位5件に絞ってトークン節約）

エントリポイント: `main.py`（CLI）、`app.py`（Streamlit Web UI）

## 送料ルール（shops.json）

各ショップの`shipping`（基本送料）と`free_threshold`（送料無料条件、nullは無料なし）を定義。未登録ショップは`_default`ルールが適用される。
