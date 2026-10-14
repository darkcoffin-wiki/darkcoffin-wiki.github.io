"""Why does 黑柩-北沙篇花絮总集篇二.docx report as missing?"""
import io
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WPS = r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing\filecache\WPSDrive\240050742\WPS云盘"
print("WPS dir exists:", os.path.isdir(WPS))
names = os.listdir(WPS)
hits = [n for n in names if "北沙篇" in n or "花絮" in n or "长歌" in n]
print("candidates in WPS dir:")
for h in hits:
    print("   ", repr(h), os.path.getsize(os.path.join(WPS, h)))

src = open(r"E:\DSHwork\heijiu\wiki\build_v6.py", encoding="utf-8").read()
for line in src.split("\n"):
    if "北沙篇花絮总集篇二.docx" in line and "WPS" in line:
        lit = line.split('r"')[1].split('"')[0]
        print("\nliteral in script:")
        print("   ", lit)
        print("   exists:", os.path.exists(lit))
        d = os.path.dirname(lit)
        print("   dirname exists:", os.path.isdir(d))
        print("   basename:", os.path.basename(lit))
        same = [n for n in names if n.startswith("黑柩-北沙篇")]
        print("   same-prefix files in dir:", same)
        for n in same:
            print("      equal to basename?", n == os.path.basename(lit), repr(n))
