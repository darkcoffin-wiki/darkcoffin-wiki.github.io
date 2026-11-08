# -*- coding: utf-8 -*-
"""改 7 份报告的封面「系列行」，统一成官网页头用的同一套编号。

**只改那段文字**：直接替换 word/document.xml 里的字符串，不动 zip 里其他条目，
也不走 python-docx 的整篇重写——这样字体、字号、对齐、缩进全部原样保留。

用法：
    python tools/report_subtitle.py --dry     # 只看命中情况
    python tools/report_subtitle.py           # 真改
"""
import io
import os
import shutil
import sys
import zipfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RD = r"E:\黑柩\黑柩报告"
BAK = os.path.join(RD, "_备份-改编号前")
MID = "\u00b7"          # 「·」U+00B7（docx 里用的就是它，不是 U+30FB）

# (文件名, 旧串, 新串)
JOBS = [
    ("黑柩报告-三大恨与李天下.docx",
     "——《黑柩》设定研究之十七",
     "——《黑柩》报告系列之十九" + " " + MID + " 跑团集锦"),
    ("黑柩报告-竖棺.docx",
     "——《黑柩》跑团集锦之三",
     "——《黑柩》报告系列之二十" + " " + MID + " 跑团集锦"),
    ("黑柩报告-青都事变.docx",
     "——《黑柩》跑团集锦之四",
     "——《黑柩》报告系列之二十一" + " " + MID + " 跑团集锦"),
    ("黑柩报告-来世乐土.docx",
     "黑柩报告系列",
     "——《黑柩》报告系列之十六" + " " + MID + " 独立作品研究之一"),
    ("黑柩报告-人鱼小队.docx",
     "黑柩报告系列" + " " + MID + " 独立作品研究之二",
     "——《黑柩》报告系列之十七" + " " + MID + " 独立作品研究之二"),
    ("黑柩报告-黑柩校园.docx",
     "黑柩报告系列" + " " + MID + " 独立作品研究之三",
     "——《黑柩》报告系列之十八" + " " + MID + " 独立作品研究之三"),
    ("黑柩报告-叶心.docx",
     "——《黑柩》设定研究之十六",
     "——《黑柩》报告系列（待编号）"),
]


def edit(path, old, new, dry):
    with zipfile.ZipFile(path) as z:
        items = [(i, z.read(i.filename)) for i in z.infolist()]
    hit = 0
    out = []
    for info, data in items:
        if info.filename == "word/document.xml":
            xml = data.decode("utf-8")
            hit = xml.count(old)
            if hit == 1:
                xml = xml.replace(old, new)
                data = xml.encode("utf-8")
            elif hit:
                raise SystemExit("命中 %d 次，不敢改：%s / %s"
                                 % (hit, os.path.basename(path), old))
        out.append((info, data))
    if hit != 1:
        raise SystemExit("没命中（%d 次）：%s / %s"
                         % (hit, os.path.basename(path), old))
    if dry:
        return hit
    tmp = path + ".new"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for info, data in out:
            zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
            zi.compress_type = info.compress_type
            zi.external_attr = info.external_attr
            z.writestr(zi, data)
    os.replace(tmp, path)
    return hit


def main():
    dry = "--dry" in sys.argv
    if not dry:
        os.makedirs(BAK, exist_ok=True)
    for fn, old, new in JOBS:
        p = os.path.join(RD, fn)
        if not os.path.exists(p):
            raise SystemExit("找不到：" + p)
        if not dry:
            # 先备份**改前**的原件（已存在就不覆盖，免得二次运行把改后的盖上去）
            dst = os.path.join(BAK, fn)
            if not os.path.exists(dst):
                shutil.copy2(p, dst)
        n = edit(p, old, new, dry)
        print("%-28s %s\n    - %s\n    + %s"
              % (fn, "命中 %d 处" % n, old, new))
    print("\n%s" % ("（dry run，未写盘）" if dry else "已写盘；原件备份在 " + BAK))


if __name__ == "__main__":
    main()
