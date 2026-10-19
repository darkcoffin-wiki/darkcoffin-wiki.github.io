"""严格验证 docs/records/session/*.tsv 里不含 QQ 号。

用法（在仓库根目录）：
    python tools/verify_records_privacy.py

为什么需要「严格版」：
    序号列本身就是 5~6 位数字（如 5216），用 `\\t\\d{5,12}\\t` 这类正则粗筛
    会把 9000 多条序号误报成账号。必须按列判断，并且要拿真实 QQ 号做比对。
"""
import collections
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RD = os.path.join(W, "docs", "records", "session")
SRC = r"E:\黑柩\黑柩跑团记录-整理\归一数据\全部消息.tsv"

# ── ① 真实 QQ 号样本（源文件不在时跳过这一项）──
real_qq = set()
if os.path.exists(SRC):
    with io.open(SRC, encoding="utf-8") as fh:
        hdr = next(fh).rstrip("\n").split("\t")
        if "QQ" in hdr:
            iq = hdr.index("QQ")
            for ln in fh:
                p = ln.rstrip("\n").split("\t")
                if len(p) > iq and p[iq].strip():
                    real_qq.add(p[iq].strip())
    print("原始 QQ 列：%d 个不同值" % len(real_qq))
else:
    print("⚠️  找不到源文件，跳过分项 ②（仍会做 ①③）")

# ── ② 扫描切片 ──
files = [f for f in sorted(os.listdir(RD)) if f.endswith(".tsv")]
suspect_names = collections.Counter()
numeric_any = collections.Counter()
hit_qq = 0
rows = 0

for f in files:
    with io.open(os.path.join(RD, f), encoding="utf-8") as fh:
        head = next(fh).rstrip("\n").split("\t")
        iSeq = head.index("序号")
        iName = head.index("规范名")
        for ln in fh:
            cells = ln.rstrip("\n").split("\t")
            if len(cells) < len(head):
                continue
            rows += 1
            nm = cells[iName].strip()
            if re.fullmatch(r"\d{5,12}", nm):
                suspect_names[nm] += 1
            for j, c in enumerate(cells):
                if j == iSeq:
                    continue
                v = c.strip()
                if real_qq and v in real_qq:
                    hit_qq += 1
                if re.fullmatch(r"\d{7,12}", v):
                    numeric_any[v] += 1

print("扫描 %d 个切片，%d 行" % (len(files), rows))
print()
print("① 规范名是纯数字的行：%d %s"
      % (sum(suspect_names.values()),
         dict(suspect_names.most_common(5)) if suspect_names else ""))
print("② 非序号列里等于真实 QQ 号的单元格：%d" % hit_qq)
print("③ 非序号列里形如 7-12 位纯数字的单元格：%d" % sum(numeric_any.values()))
if numeric_any:
    print("   示例：%s" % dict(numeric_any.most_common(8)))
print()
ok = (hit_qq == 0 and not suspect_names and not numeric_any)
print("结论：%s" % ("✅ 未发现 QQ 号" if ok else "❌ 需要处理"))
sys.exit(0 if ok else 1)
