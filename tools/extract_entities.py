#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""实体候选抽取（确定性，无模型）。

对 210 篇正文做字符 n-gram 统计，用「左右邻接多样性（边界熵）」区分
「成词」（如 叶心、陆柩）与「短语碎片」（如 她的、说的是）。

产出：data/entity_candidates.json
    {
      "people_candidates": [...],   # 姓+1~2 字、通过边界熵过滤
      "proper_candidates": [...],   # 通用高频专名候选（机构/地名）
      "stats": {...}
    }

用法：python tools/extract_entities.py
"""
import glob
import json
import math
import os
import re
import collections
import sys

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(W, "source")
DATA = os.path.join(W, "data")

# ---------------------------------------------------------------- 停用字
# 出现在候选内部就基本可以判定「不是专名」的字
STOP = set(
    "的了是在有和与及也就都而但或如果因为所以这那这些那些一个"
    "不没有很更最太再又还只从到对向被把让使给对于关于按照根据"
    "我可以你他她它们我们你们他们自己什么怎么为什么怎样如何"
    "上下里中外前后左右中之间时候已经正在将要能够会要想说"
    "一二三四五六七八九十百千万亿第几个条只件种位名次"
    "来去出入过起来着得地着吗呢吧啊呀哦嗯哈嘿喂么"
    "人们东西事情问题地方方面情况时间时候样子"
    "知道觉得认为看到听到感到开始继续进行出现成为"
    "虽然然而并且而且不过然后于是因此于是"
    "与之其此该某各每任何所有全部整个"
    "以于由自当则乃即且并亦乃"
)

# 允许出现在专名里的字（用于放宽：姓+字 情形）
SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
    "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
    "虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚"
    "程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓"
    "牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭历戎祖武符刘景詹束龙"
    "叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双"
    "闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农"
    "温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘"
    "匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
    "曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)

# 语料里大量出现的「类名/职务」，单独列出便于人工判定
ROLE_HINT = re.compile(
    r"(先生|小姐|女士|同志|阁下|大人|将军|上校|中校|少校|大校|元帅|总统|主席|"
    r"总理|部长|局长|处长|科长|队长|组长|社长|会长|校长|院长|所长|厂长|经理|"
    r"董事|总裁|主任|书记|委员|议员|代表|大使|领事|法官|律师|医生|护士|教授|"
    r"老师|同学|先生|夫人|太太|陛下|殿下|教皇|主教|大主教|神父|牧师|修女|"
    r"帮主|堂主|香主|掌柜|老板|队长|班长|排长|连长|营长|团长|旅长|师长|军长)"
)


def clean(text):
    """去掉 frontmatter 与 markdown 噪声，只留正文散文+对白。"""
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4:]
    text = re.sub(r"^\s*#.*$", " ", text, flags=re.M)      # 标题行
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)            # 加粗
    text = re.sub(r"[*_`>\[\]()（）【】「」『』《》…—\-–·、，。！？；：\"'“”‘’\s]+", " ", text)
    return text


def ngrams(seg, lo=2, hi=6):
    n = len(seg)
    for size in range(lo, hi + 1):
        for i in range(n - size + 1):
            yield seg[i:i + size]


def main():
    files = sorted(glob.glob(os.path.join(SRC, "hx-*.md")))
    if not files:
        sys.exit("no source files")
    all_text = []
    for f in files:
        t = open(f, encoding="utf-8").read()
        all_text.append(clean(t))
    corpus = "  ".join(all_text)          # 双空格作句子边界，避免跨篇成词

    freq = collections.Counter()
    left = collections.defaultdict(collections.Counter)
    right = collections.defaultdict(collections.Counter)
    for seg in re.split(r"\s+", corpus):
        if len(seg) < 2:
            continue
        # 只在句读切出的片段内统计，边界字符记为 #
        s = "#" + seg + "#"
        for size in range(2, 7):
            for i in range(len(s) - size + 1):
                g = s[i:i + size]
                if "#" in g[1:-1]:
                    continue
                freq[g] += 1
                left[g][s[i - 1] if i > 0 else "#"] += 1
                right[g][s[i + size] if i + size < len(s) else "#"] += 1

    def entropy(counter):
        total = sum(counter.values())
        if total == 0:
            return 0.0
        return -sum((c / total) * math.log(c / total) for c in counter.values())

    def score(g):
        return min(entropy(left[g]), entropy(right[g]))

    def has_stop(g):
        return any(ch in STOP for ch in g)

    people = []
    proper = []
    for g, c in freq.items():
        if c < 4:
            continue
        # 前导/尾随标点或数字噪音
        if g[0].isdigit() or g[-1].isdigit():
            continue
        if has_stop(g):
            continue
        ent = score(g)
        rec = {
            "tag": g,
            "count": c,
            "entropy": round(ent, 3),
            "is_role": bool(ROLE_HINT.search(g)),
            "has_surname": g[0] in SURNAMES,
        }
        if g[0] in SURNAMES and 2 <= len(g) <= 4:
            people.append(rec)
        if 2 <= len(g) <= 6 and ent >= 1.0:
            proper.append(rec)

    people.sort(key=lambda r: (-r["count"], r["tag"]))
    proper.sort(key=lambda r: (-r["count"], r["tag"]))

    out = {
        "note": "确定性 n-gram 候选，供人工/模型审核后写入 vocabulary.json",
        "corpus_files": len(files),
        "people_candidates": people,
        "proper_candidates": proper,
        "stats": {
            "people_candidates": len(people),
            "proper_candidates": len(proper),
            "ngram_total": len(freq),
        },
    }
    os.makedirs(DATA, exist_ok=True)
    with open(os.path.join(DATA, "entity_candidates.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print(json.dumps(out["stats"], ensure_ascii=False))
    print("wrote", os.path.join(DATA, "entity_candidates.json"))


if __name__ == "__main__":
    main()
