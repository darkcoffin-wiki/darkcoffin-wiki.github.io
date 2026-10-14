"""Why did 总集篇 一二三四五 yield 0 title cards? Inspect their markup."""
import io
import re
import sys
import urllib.request

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
KIND = re.compile(r"^(花絮|楔子|画外音|长歌|剧情花絮|特别内容|四格|特别环节|四格漫画)\s*[:：]")


def get(url):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                  timeout=40).read().decode("utf-8", "ignore")


for aid in (264, 277, 289, 476, 484):
    html = get(f"https://darkcoffin.hubingsf.cn/archives/{aid}")
    print("=" * 70)
    print(f"archives/{aid}  html {len(html)} chars")

    # find every line/segment that mentions a kind + colon
    hits = [m.start() for m in re.finditer(r"(花絮|楔子|画外音|长歌)\s*[:：]", html)]
    print(f"  raw occurrences of kind+colon: {len(hits)}")

    # show the markup context of the first 6
    for h in hits[:6]:
        seg = html[max(0, h - 220):h + 140]
        seg = re.sub(r"\s+", " ", seg)
        print(f"  ...{seg}...")
        print("  " + "-" * 60)

    # what element types wrap them?
    tags = re.findall(r"<(\w+)[^>]*>\s*(?:<[^>]+>\s*)*(花絮|楔子|画外音|长歌)\s*[:：]", html)
    print(f"  wrapping tags: {tags[:14]}")

    # any element with class containing title/card/heading?
    cls = set(re.findall(r'class="([^"]*(?:title|card|heading|entry|post)[^"]*)"', html))
    print(f"  classes mentioning title/card/heading: {list(cls)[:12]}")
