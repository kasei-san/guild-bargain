"""Claude CLI でカード名を正規化する"""

import json
import subprocess


def normalize_card_names(card_names: list[str]) -> list[str]:
    """カード名をMTGの正式名称に正規化する"""

    prompt = f"""以下のMTGカード名リストを、Wisdom Guild（日本語MTGカード検索サイト）で検索可能な正式名称に正規化してください。

入力リスト:
{json.dumps(card_names, ensure_ascii=False)}

ルール:
- 日本語名はそのまま日本語の正式名称にする（記号の有無も正確に）
- 英語名はそのまま英語の正式名称にする
- 明らかな誤字・表記揺れを修正する（例: 「皆に命を」→「皆に命を！」）
- 存在しないカード名は "UNKNOWN: 元の名前" とする

以下のJSON配列のみを出力してください。説明不要。
["正規化されたカード名1", "正規化されたカード名2", ...]"""

    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude CLI エラー: {result.stderr}")

    # JSON配列を抽出
    output = result.stdout.strip()
    # コードブロック内にある場合を考慮
    if "```" in output:
        lines = output.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.startswith("```"):
                in_block = not in_block
                continue
            if in_block:
                json_lines.append(line)
        output = "\n".join(json_lines)

    return json.loads(output)
