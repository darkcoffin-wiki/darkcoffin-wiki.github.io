"""Restore the correct path for 黑柩-北沙篇花絮总集篇二.docx (WPS dir only)."""
import io
import os
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

P = r"E:\DSHwork\heijiu\wiki\build_v6.py"
WRONG = r"E:\黑柩\黑柩小说花絮\黑柩-北沙篇花絮总集篇二.docx"
RIGHT = (r"C:\Users\fly12138\AppData\Local\Kingsoft\WPS Cloud Files\userdata\qing"
         r"\filecache\WPSDrive\240050742\WPS云盘\黑柩-北沙篇花絮总集篇二.docx")

t = open(P, encoding="utf-8").read()
print("wrong path present:", WRONG in t)
print("right path present:", RIGHT in t)
print("right path exists :", os.path.exists(RIGHT))

if WRONG in t:
    t = t.replace(WRONG, RIGHT)
    open(P, "w", encoding="utf-8").write(t)
    print("-> replaced")
elif RIGHT in t:
    print("-> already correct, nothing to do")
else:
    print("!! neither found; inspect SOURCES manually")
