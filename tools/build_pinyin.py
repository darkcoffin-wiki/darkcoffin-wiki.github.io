#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""建立「汉字→无声调拼音」表，用于生成英文 slug。

数据源：Unihan kMandarin（mozillazg/pinyin-data 的 kMandarin.txt），
首次运行会下载到 data/_kMandarin.txt 并缓存。

用法：python tools/build_pinyin.py
产出：data/pinyin_table.json
"""
import json
import os
import re
import unicodedata
import urllib.request

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(W, "data")
URL = "https://raw.githubusercontent.com/mozillazg/pinyin-data/master/kMandarin.txt"
CACHE = os.path.join(DATA, "_kMandarin.txt")

TONE_MAP = {
    "ā": "a", "á": "a", "ǎ": "a", "à": "a",
    "ē": "e", "é": "e", "ě": "e", "è": "e",
    "ī": "i", "í": "i", "ǐ": "i", "ì": "i",
    "ō": "o", "ó": "o", "ǒ": "o", "ò": "o",
    "ū": "u", "ú": "u", "ǔ": "u", "ù": "u",
    "ǖ": "v", "ǘ": "v", "ǚ": "v", "ǜ": "v", "ü": "v",
    "ń": "n", "ň": "n", "ǹ": "n", "ḿ": "m",
}


def strip_tone(s):
    s = "".join(TONE_MAP.get(c, c) for c in s)
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower()


def ensure_cache():
    if os.path.exists(CACHE) and os.path.getsize(CACHE) > 100000:
        return
    os.makedirs(DATA, exist_ok=True)
    with urllib.request.urlopen(URL, timeout=60) as r, open(CACHE, "wb") as fh:
        fh.write(r.read())


def main():
    ensure_cache()
    table = {}
    multi = {}
    for line in open(CACHE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^U\+([0-9A-F]+):\s*([^#]+?)\s*(?:#.*)?$", line)
        if not m:
            continue
        cp = int(m.group(1), 16)
        readings = [r.strip() for r in m.group(2).split(",") if r.strip()]
        if not readings:
            continue
        first = strip_tone(readings[0])
        first = re.sub(r"[^a-z]", "", first)
        if not first:
            continue
        ch = chr(cp)
        table[ch] = first
        if len(readings) > 1:
            multi[ch] = [strip_tone(r) for r in readings]

    out = {
        "meta": {"source": URL, "note": "汉字→无声调拼音（取 kMandarin 首选读音）",
                 "glyphs": len(table), "multi_reading": len(multi)},
        "table": table,
        "multi": multi,
    }
    with open(os.path.join(DATA, "pinyin_table.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=0)
    print(json.dumps(out["meta"], ensure_ascii=False))


if __name__ == "__main__":
    main()
