"""価格データのキャッシュ管理"""

import json
import os
import time
import urllib.parse

CACHE_DIR = os.path.join(".cache", "prices")
CACHE_TTL = 86400  # 24時間


def _cache_path(card_name: str) -> str:
    """カード名からキャッシュファイルパスを生成する"""
    encoded = urllib.parse.quote(card_name, safe="")
    return os.path.join(CACHE_DIR, f"{encoded}.json")


def get_cached(card_name: str) -> list[dict] | None:
    """キャッシュが存在し24h以内ならデータを返す。なければNone"""
    path = _cache_path(card_name)
    if not os.path.exists(path):
        return None

    try:
        with open(path) as f:
            cache = json.load(f)
        if time.time() - cache["timestamp"] < CACHE_TTL:
            return cache["data"]
    except (json.JSONDecodeError, KeyError, OSError):
        pass

    return None


def set_cache(card_name: str, data: list[dict]) -> None:
    """キャッシュに保存する"""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = _cache_path(card_name)
    with open(path, "w") as f:
        json.dump({"timestamp": time.time(), "data": data}, f, ensure_ascii=False)


def cleanup_expired() -> None:
    """期限切れキャッシュファイルを削除する"""
    if not os.path.isdir(CACHE_DIR):
        return

    now = time.time()
    for filename in os.listdir(CACHE_DIR):
        if not filename.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, filename)
        try:
            with open(path) as f:
                cache = json.load(f)
            if now - cache["timestamp"] >= CACHE_TTL:
                os.remove(path)
        except (json.JSONDecodeError, KeyError, OSError):
            os.remove(path)
