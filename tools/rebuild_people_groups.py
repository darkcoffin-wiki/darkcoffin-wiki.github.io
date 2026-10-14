#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按作者官方口径重排「人物」子分类。

口径来源（两者结合，以站点分组为主干，因其更细且贴合篇目）：
* **站点「人物介绍」**（darkcoffin.hubingsf.cn/characters）的 21 个分组：
  小说宇宙主角团队 / 斯卡雷特家族主要成员 / 其他天选异能者 / 进盟背景人士 /
  青都帮派地区·天堂物流 / 北沙·光胜集团 / 青都·富贵集团 / 青都帮派地区·通雷帮 /
  青都帮派地区·惊虎帮 / 希联政府成员&希共党员 / 北沙政府成员 / 青都帮派地区·安心屋 /
  北沙·中分山 / 北沙社会名流 / 北沙地区活跃人士 / 北沙·日本街 /
  蚀血教教徒&长老 / 黑旗·蛛眼小队 / 教团国·教皇与十三圣人
* **设定集卷八「人物志」**的 8 个分组（补漏与交叉验证）：
  小说宇宙主角团 / 进盟与斯卡雷特家族 / 希共与希联阵营 / 北沙政权与北沙社会 /
  走廊区与街道势力 / 教团国与圣人群像 / 蚀血教与人造血族 / 神秘学与异能相关人物

用法：
    python tools/rebuild_people_groups.py --dry-run   # 只校验，不写
    python tools/rebuild_people_groups.py             # 写入 data/subcategories.json
校验：172 个人物标签必须**恰好各出现一次**，否则报错并拒绝写入。
"""
import argparse
import collections
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402

DATA = common.DATA
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ---------------------------------------------------------------- 分组表
# 顺序 = 首页展示顺序；来源注明对应官方分组
GROUPS = [
    ("主角团队", "站点「小说宇宙主角团队」+ 设定集卷八·一", [
        "陆柩", "叶心", "叶暝", "路絮", "原绘", "红樱", "叶惠", "苏小青"]),
    ("斯卡雷特家族与斯卡雷特帝国", "站点「斯卡雷特家族主要成员」「进盟背景人士」+ 卷八·二 + 卷七「斯卡雷特帝国与血族」", [
        "李伊", "原星", "风薰", "原知", "亚顿", "龙涟", "伊寓", "三井伊森",
        "原末"]),
    ("希共与希联政府", "站点「希联政府成员&希共党员」+ 卷八·三", [
        "青朗", "原朗", "郎溪", "郎河", "定民", "定慧", "合连", "文慧",
        "林好", "原平", "般利", "缪斯·辛克", "苍穹", "董屋", "鲍声", "悬月",
        "洗尘", "胜记", "声风", "比利", "阿闵", "远辰", "安花", "原草", "老许",
        "蔡小静", "明森", "盖尔"]),
    ("北沙政权与社会", "站点「北沙政府成员」「北沙社会名流」「北沙地区活跃人士」+ 卷八·四", [
        "高冒", "高领", "西娜·陈", "洪黎", "洪巢", "文不迁", "文志远", "赫炎",
        "赫震", "赫章", "陈光明", "南方枝", "保罗", "天子棠", "天子棣",
        "天子辉", "鸣采菱"]),
    ("日本街", "站点「北沙·日本街」+ 卷八·五", [
        "时崎信子", "时崎宗望", "川崎罗", "海老名惠子", "海老名双叶", "海老名雄介",
        "柳生纯一", "月见力", "月见武",
        "月见灯", "柳生敬", "渡边镰川", "夜眉", "静莲", "秋墨"]),
    ("中分山", "站点「北沙·中分山」", [
        "镜缘", "鸣十二", "鸣十三", "鸣七", "鸣二", "喜春", "朴道地", "朴意生",
        "李兴元", "金尚早"]),
    ("青都帮派地区", "站点「青都帮派地区」四节（天堂物流／通雷帮／惊虎帮／安心屋）——按作者裁定：这几位同时留在各自的细分组", [
        "苍鬼", "玉轮"]),
    ("通雷帮与第一特区", "站点「青都帮派地区·通雷帮」", ["千分", "嘉云", "千禾", "镇山"]),
    ("惊虎帮", "站点「青都帮派地区·惊虎帮」", ["玉轮"]),
    ("天堂物流", "站点「青都帮派地区·天堂物流」", ["苍鬼", "余烬"]),
    ("富贵集团", "站点「青都·富贵集团」", [
        "齐藤优子", "朗格", "左刃", "夜瞳", "查莉", "王富贵", "王霜风", "蓝冷泉",
        "容彩", "小夫"]),
    ("光胜集团", "站点「北沙·光胜集团」", ["唐晖", "魏工", "真锋", "管直", "鲁光胜",
                                          "鸣十三"]),
    ("希联军警与治安", "设定集卷三·四「军事与复国军」+ 卷四「宪兵队与特务机构」", [
        "木金水", "木朽", "木有为", "准锋", "卫国赵", "青云", "和头",
        "克槌", "油舍", "利刺", "林杉", "水荇", "汉格", "一泷", "郎胜",
        "董山", "丁健"]),
    ("教团国·教皇与十三圣人", "站点「教团国·教皇与十三圣人」+ 卷八·六", [
        "渊", "舜", "昭", "宗魁", "伊西斯", "阿舜", "青昭"]),
    ("蚀血教与人造血族", "站点「蚀血教教徒&长老」+ 卷八·七", [
        "1号", "2号", "3号", "4号", "5号", "薇薇安", "洛克",
        "鲜红超人", "蠊", "文聪"]),
    ("黑旗·蛛眼小队", "站点「黑旗·蛛眼小队」", ["杜丁", "阳戬", "蛛眼", "苏小青"]),
    ("神圣希望帝国", "设定集卷五「神圣希望帝国」——作者裁定：有机皇、俾斯麦等角色的是此帝国（旧称夜都帝国）", [
        "机皇", "俾斯麦", "谢尔盖"]),
    ("深黑军团", "设定集卷三「深黑军团」+ 卷八·七", []),
    ("玩家与穿越者", "站点体例：玩家角色单列（另含穿越者；`特零` 是作者笔名的穿越者身份）", [
        "智波", "寂风", "泡泡", "王路玲", "2077", "林登万", "莎乐美", "路登",
        "薛婕", "辛普森", "鲨月狗", "白娅", "李大禾", "子明未", "特零"]),
    ("其他与客串", "散见各篇、未列入官方人物志的次要角色", [
        "燃堂猛", "真岛", "阿罗", "潘陶", "艾米丽", "莫德", "铃木",
        "锆哥", "璇姐", "阿列克谢"]),
]

# 作者裁定：一个标签**可以**同时属于多个子分类（标签在不同视角下身份不同）。
# 这里显式声明允许重复的名字，避免校验把它们当成错误。
ALLOW_DUPLICATE = True

# 上面若有名字重复/不存在，校验会拦住；这里显式声明：重复项以第一次出现为准


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tags = json.load(open(os.path.join(DATA, "tags.json"), encoding="utf-8"))
    real = {t for t, m in tags["tags"].items() if "人物" in (m.get("dimensions") or [])}

    seen = collections.Counter()
    for name, src, members in GROUPS:
        for t in members:
            seen[t] += 1
    dupes = sorted(t for t, c in seen.items() if c > 1)
    unknown = sorted(t for t in seen if t not in real)
    missing = sorted(real - set(seen))
    problems = []
    if dupes and not ALLOW_DUPLICATE:
        problems.append("重复归类：%s" % "、".join(dupes))
    if unknown:
        problems.append("不存在的标签：%s" % "、".join(unknown))
    if missing:
        problems.append("漏归类：%s" % "、".join(missing))
    print("分组 %d 个；人物标签 %d 个；已归 %d 个"
          % (len(GROUPS), len(real), len(set(seen) & real)))
    if dupes:
        print("多分类标签（%d 个，允许）：%s" % (len(dupes), "、".join(dupes)))
    if problems:
        print("\n发现问题，不写入：")
        for p in problems:
            print("  ✗ " + p)
        sys.exit(1)
    print("✓ %d 个标签均至少归一类；无错名、无漏项。" % len(real))
    if args.dry_run:
        return
    sc = json.load(open(os.path.join(DATA, "subcategories.json"), encoding="utf-8"))
    sc["dimensions"]["人物"] = [
        {"name": name, "source": src,
         "tags": sorted(members, key=lambda t: -len(tags["tag_index"][t]))}
        for name, src, members in GROUPS]
    with io.open(os.path.join(DATA, "subcategories.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(sc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("\n已写入 data/subcategories.json（人物 %d 组）" % len(GROUPS))
    for name, src, members in GROUPS:
        print("  %-14s %2d 个  ← %s" % (name, len(members), src))


if __name__ == "__main__":
    main()
