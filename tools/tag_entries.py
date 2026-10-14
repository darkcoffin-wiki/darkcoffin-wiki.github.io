#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对 210 篇花絮打标签（确定性，可重复运行，增量友好）。

设计要点
--------
* **确定性**：同一份语料 + 同一份词表，永远产出同一份结果（无随机、无外部调用）。
* **A/B/J 机械提取**：文类、叙事层级、篇幅——零成本、零歧义。
* **C 实体 / I 剧情线 / 时间**：受控词表匹配（词表见 data/vocab_*.json），
  长词优先且不重复计数；命中即打，篇内计权（出现次数）。
* **D 主题 / E 事件 / F 关系 / G 基调**：受控关键词表匹配
  （data/vocab_dimensions.json），带最小命中阈值与篇内上限。
* **防漂移**：任何标签都必须能在词表里找到规范写法；脚本不会自创标签。
  若匹配到词表外的写法，进 `unmapped` 报告，供人工审核后并入词表。
* **增量**：结果里存 `source_hash`；`--only-new` 只对新增/变更条目重算。

用法
----
    python tools/tag_entries.py                # 全量重算
    python tools/tag_entries.py --only-new     # 只算 hash 有变化的条目
    python tools/tag_entries.py --report       # 额外打印标签分布报告
产出
----
    data/tags.json          条目 → 标签；标签 → 条目（站点客户端读这个）
    data/slugs.json         中文标签 → 英文 slug
    data/tag_report.md      标签分布 + 未映射报告（人工审核用）
"""
import argparse
import collections
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common  # noqa: E402
import grading as grading_mod  # noqa: E402

W = common.W
DATA = common.DATA

# ------------------------------------------------------------------ 机械表
KIND_LAYER = {
    "花絮": ["已发生"],
    "剧情花絮": ["已发生"],
    "特别环节": ["已发生"],
    "特别内容": ["已发生"],
    "四格漫画": ["已发生"],
    "四格": ["已发生"],
    "长歌": ["已发生"],
    # 楔子：作者 2026-10-14 修定的定义——
    # 「未来可能发生的事情，或**已经发生并为未来做铺垫的事情**」
    # 所以楔子不再等同于「未发生」：正文里若明确在为将来铺垫，则同时打「已发生」。
    "楔子": ["未来可能"],
    "画外音": ["平行世界线"],
}

# 「铺垫」证据：出现这些词说明本篇叙述的是**已发生、且为将来铺路**的事
FORESHADOW = re.compile(
    r"铺垫|伏笔|作为.{0,8}楔子|为.{0,10}(将来|未来|日后|以后).{0,8}(做|作)?准备"
    r"|埋下|前情|此前.{0,6}已经|这是.{0,6}之后|正是.{0,6}起因|开端")

# 旧 taxonomy 里的写法 → 语料实际 kind 的归并
KIND_ALIAS = {
    "四格": "四格漫画",
    "玩家之声": "特别内容",
}


def layers_for(kind, body):
    """文类 → 叙事层级列表（楔子可能同时是「未来可能」与「已发生」）。"""
    layers = list(KIND_LAYER.get(kind, []))
    if kind == "楔子" and FORESHADOW.search(body):
        layers.append("已发生")
    return layers


def length_tag(chars):
    if chars < 1500:
        return "短篇"
    if chars > 8000:
        return "长篇"
    return "中篇"


# 主标签优先级（数字越小越靠前）
PRIORITY = {
    "文类": 0, "叙事层级": 9, "篇幅": 9,
    "人物": 1, "剧情线": 2, "组织": 3, "地理": 4,
    "设施": 5, "主题": 6, "事件类型": 6, "关系": 7, "主题词": 7, "时间": 8,
}

DIM_OF = {          # 受控标签 → 维度
    "人物": "人物", "组织": "组织", "地理": "地理", "设施": "设施",
    "剧情线": "剧情线",
}


# ------------------------------------------------------------ 词表装载
def load_overrides():
    p = os.path.join(DATA, "taxonomy_overrides.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding="utf-8"))


def load_vocab():
    """返回 (标签词典, 匹配表, 实体原始表, 覆盖表)。

    标签词典 tag -> {label, dimensions[list], doc_freq, variants}
        **dimensions 是列表**：同一个标签可以属于多个维度（如 长歌＝文类+剧情线）。
    匹配表 [(variant, canonical_label, dimension)]，长词优先；允许同词多分面。
    归并统一走 data/taxonomy_overrides.json（人工可审），词表文件保留原始证据。
    """
    ov = load_overrides()
    alias = {}
    for key in ("实体同义（variant → 受控标签）", "人物同义（variant → 受控人名）"):
        for k, v in (ov.get(key) or {}).items():
            alias[k] = v
    suppress = set(ov.get("需要抑制的泛称（不做标签）") or [])
    suppress |= set(ov.get("人名噪声（从词表剔除，不产出标签）") or {})
    # 同名降级：同一名字在**指定维度**上是误标（去掉词表口径错误造成的假重合）。
    # 用 (维度, 名字) 配对，避免同一名字同时是正当人物标签、又在组织维度上需要降级时互相干扰。
    # 名字同时算上它的**规范写法**（如 大禾→李大禾），否则别名会把降级绕过去。
    drop_pairs = set()
    drop_note = {}
    for name, rule in (ov.get("同名降级（同一名字只保留指定维度，去掉误标的分面）") or {}).items():
        if isinstance(rule, dict) and rule.get("drop"):
            names = {name, alias.get(name, name)}
            for d in rule["drop"]:
                for n in names:
                    drop_pairs.add((d, n))
                drop_note[(d, name)] = rule.get("why", "")

    labels = {}
    matchers = []
    entities = {}

    def add(label, dimension, variants=(), doc_freq=0):
        label = (label or "").strip()
        if not label or label in suppress:
            return
        if (dimension, label) in drop_pairs:
            return          # 该名字在这个维度上是误标（见 同名降级）
        canon = alias.get(label, label)
        if canon in suppress or (dimension, canon) in drop_pairs:
            return
        rec = labels.setdefault(canon, {"label": canon, "dimensions": [],
                                        "doc_freq": 0, "variants": []})
        if dimension not in rec["dimensions"]:
            rec["dimensions"].append(dimension)
        if doc_freq:
            rec["doc_freq"] = max(rec["doc_freq"], doc_freq)

        # 规范写法自己也是一个匹配串
        if canon not in rec["variants"]:
            rec["variants"].append(canon)
        matchers.append((canon, canon, dimension))

        # **变体是别名，不是新标签**：登记为「写法 → canon」的匹配串。
        # （早期实现把变体也当成独立标签，导致 `皇宫` 和 `皇城` 各占一个标签。）
        for v in variants:
            v = (v or "").strip()
            if not v or v in suppress or v == canon:
                continue
            target = alias.get(v, canon)          # 变体另有显式归并时以它为准
            if target in suppress or (dimension, target) in drop_pairs:
                continue
            trec = labels.setdefault(target, {"label": target, "dimensions": [],
                                              "doc_freq": 0, "variants": []})
            tdims = trec["dimensions"] or ([dimension] if target == canon else [])
            for d in tdims:
                matchers.append((v, target, d))

        for v, target in list(alias.items()):
            if not v or v in suppress or (dimension, target) in drop_pairs:
                continue
            trec = labels.get(target)
            if not trec or dimension not in trec["dimensions"]:
                continue
            if not any(m[0] == v and m[1] == target and m[2] == dimension
                       for m in matchers):
                matchers.append((v, target, dimension))
                if v not in trec["variants"]:
                    trec["variants"].append(v)
            if v not in trec["variants"]:
                trec["variants"].append(v)

    # -- 人物
    p = os.path.join(DATA, "vocab_people.json")
    if os.path.exists(p):
        v = json.load(open(p, encoding="utf-8"))
        for r in v.get("people", []):
            if r.get("kind", "person") != "person":
                continue
            add(r["tag"], "人物", r.get("variants", ()), r.get("entries", 0))

    # -- 组织 / 地理 / 设施 / 剧情线（同一标签可出现在多个分面，全部登记）
    p = os.path.join(DATA, "vocab_entities.json")
    if os.path.exists(p):
        entities = json.load(open(p, encoding="utf-8"))
        for key, dim in (("orgs", "组织"), ("places", "地理"),
                         ("facilities", "设施"), ("series", "剧情线")):
            for r in entities.get(key, []):
                tag = (r.get("tag") or "").strip()
                if tag:
                    add(tag, dim, r.get("variants", ()), r.get("entries", 0))

    # 语义维度的受控标签也登记进标签词典：这样「背叛」这类**同时属于主题词与关系**的
    # 标签，即使本次只有一边的规则命中，也能保留它固有的全部维度。
    dims_spec = load_dimensions()
    for dim in ("主题", "事件类型", "关系", "主题词", "时间"):
        for lab in (dims_spec.get(dim) or {}):
            if lab in suppress or (dim, lab) in drop_pairs:
                continue
            rec = labels.setdefault(lab, {"label": lab, "dimensions": [],
                                          "doc_freq": 0, "variants": []})
            if dim not in rec["dimensions"]:
                rec["dimensions"].append(dim)

    # 文类与叙事层级：语料固定值，也登记进标签词典（便于维度展示）
    for k in ("花絮", "楔子", "画外音", "剧情花絮", "特别环节",
              "特别内容", "四格漫画", "长歌"):
        labels.setdefault(k, {"label": k, "dimensions": [], "doc_freq": 0,
                              "variants": []})
        if "文类" not in labels[k]["dimensions"]:
            labels[k]["dimensions"].append("文类")
    for k in ("已发生", "未来可能", "平行世界线"):
        labels.setdefault(k, {"label": k, "dimensions": [], "doc_freq": 0,
                              "variants": []})
        if "叙事层级" not in labels[k]["dimensions"]:
            labels[k]["dimensions"].append("叙事层级")
    for k in ("短篇", "中篇", "长篇"):
        labels.setdefault(k, {"label": k, "dimensions": [], "doc_freq": 0,
                              "variants": []})
        if "篇幅" not in labels[k]["dimensions"]:
            labels[k]["dimensions"].append("篇幅")

    # 归并目标兜底登记
    for src, dst in alias.items():
        if dst in labels or dst in suppress:
            continue
        for (variant, canonical, dim) in matchers:
            if canonical in (dst, src):
                labels.setdefault(dst, {"label": dst, "dimensions": [dim],
                                        "doc_freq": 0, "variants": []})
                break

    matchers.sort(key=lambda m: (-len(m[0]), m[0]))

    # 包含关系补标：长名（机构驻地／设施／区域）会吃掉同句里的上级名字——
    # `纠察队总部` 一出现，`纠察队` 这个组织就再也匹配不到了（hx-041 实测）。
    # 规则：
    #   * 只从**设施/地理**名展开（这两类是「地名+机构」的复合体）
    #   * 被补的标签长度 ≥2、且**不得比来源名更长**
    #   * 来源名长度 ≥4（避免 `北沙` 这种短名把 `沙` 之类补出来）
    contained = collections.defaultdict(set)
    for long_label, rec in labels.items():
        if not (set(rec.get("dimensions") or []) & {"设施", "地理"}):
            continue
        if len(long_label) < 4:
            continue
        for sub in labels:
            if len(sub) < 2 or sub == long_label or len(sub) > len(long_label):
                continue
            if sub in long_label:
                contained[long_label].add(sub)
    return labels, matchers, entities, ov, contained


def load_dimensions():
    p = os.path.join(DATA, "vocab_dimensions.json")
    if not os.path.exists(p):
        return {}
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------------ 匹配核心
def longest_matches(body, matchers):
    """不重叠匹配：每次取当前位置最长的词，命中后跳过该词长度。

    **允许多维度**：同一个词可以命中多个分面，返回 [(label, dimension)]。
    返回 Counter: (label, dimension) -> 命中次数。
    """
    hits = collections.Counter()
    i, n = 0, len(body)
    # 按首字建索引，加速
    by_first = collections.defaultdict(list)
    for variant, label, dim in matchers:
        by_first[variant[0]].append((variant, label, dim))
    while i < n:
        cands = by_first.get(body[i])
        if not cands:
            i += 1
            continue
        matched = [(v, lbl, d) for v, lbl, d in cands if body.startswith(v, i)]
        if matched:
            best_len = max(len(v) for v, _, _ in matched)
            for v, lbl, d in matched:
                if len(v) == best_len:
                    hits[(lbl, d)] += 1
            i += best_len
        else:
            i += 1
    return hits


def auto_min(rule, floor):
    """命中阈值随该标签的关键词条数**温和**缩放。

    早期版本用 `round(k*0.4)` 封顶 6——结果是**关键词越多的标签越难命中**，
    像「恋人」（12 个关键词）要命中 5 次才算，把 hx-121《齐藤优子浪漫史》
    这种明显是恋人向的篇目全卡掉了。现改为上限 3，只用来滤掉「只蹭到一个词」的噪声。
    """
    k = len(rule.get("keywords") or [])
    return max(floor, min(3, round(k * 0.3)))


# 「关系」维度的证据强度：强词（明确的关系陈述）与弱词（泛称）分开计分。
# 目的：`恋人` 这类窄标签只出现一次强词（如「恋爱」「接吻」）就该打上，
# 而 `亲族` 只蹭到一个「父亲」不足以打标。作者 2026-10-14 授权放宽本维度。
REL_STRONG = {
    "恋人": ["恋人", "恋爱", "爱情", "接吻", "亲吻", "求婚", "结为夫妻", "情人",
            "男朋友", "女朋友", "情侣", "私奔", "妻子", "丈夫", "老公", "老婆",
            "再续前缘", "浪漫"],
    "政敌": ["政敌", "宿敌", "权力斗争", "明争暗斗", "反目", "死对头", "清洗异己"],
    "师徒": ["师父", "师傅", "师承", "拜师", "徒弟", "弟子", "学徒", "教导", "门下"],
    "背叛": ["背叛", "出卖", "叛徒", "叛变", "背刺", "反水", "变节", "倒戈"],
}
REL_WEAK = {
    "亲族": ["父亲", "母亲", "哥哥", "姐姐", "弟弟", "妹妹", "儿子", "女儿", "家族",
            "血缘", "叔叔", "舅舅", "亲人", "妈妈", "爸爸", "爸妈", "父母"],
    "上下级": ["上级", "下级", "上司", "属下", "部下", "长官", "汇报", "领导",
             "董事长", "总裁"],
    "同盟": ["同盟", "联盟", "联手", "结盟", "战友", "伙伴", "统一战线", "协力"],
    "恋人": ["结婚", "约会"],
}


def rel_score(body, label, base, rule_keywords=()):
    """关系维度的加权得分。

    强词（明确的关系陈述，如「恋爱」「接吻」）2 分，弱词（泛称，如「父亲」）1 分。
    规则自带的其它关键词（既不在强表也不在弱表里的）按 1 分计入——
    **不能减掉**：早期实现用减法抵消，把「政敌」这种规则首词算成了 0 分。
    """
    strong = REL_STRONG.get(label, [])
    weak = REL_WEAK.get(label, [])
    covered = set(strong) | set(weak)
    s = sum(2 * body.count(k) for k in strong)
    s += sum(body.count(k) for k in weak)
    for k in rule_keywords:
        if k and k not in covered:
            s += body.count(k)
    return s
SPECIFICITY = {
    "关系": ["恋人", "政敌", "师徒", "背叛", "同盟", "上下级", "亲族"],
    "主题词": ["救赎", "腐败", "复仇", "绝望", "忠诚", "牺牲", "背叛", "理想",
              "暴力", "自由", "希望"],
    "事件类型": ["起义失败", "政变", "暗杀", "清洗", "屠杀", "起义", "典礼",
                "选举", "公审", "谈判", "战争", "会议"],
    "时间": ["战后10年", "战后6年", "战后5年", "战后4年", "战后3年", "战后2年",
            "战前", "战时"],
}


def dim_hits(body, spec, floor=2, cap=3, dim="", min_override=None):
    """关键词 + 正则匹配某个维度；返回命中标签及其强度。

    * 超出 cap 时按**专指程度**（SPECIFICITY）优先保留，其次才看强度
    * `关系` 维度改用加权强度（强词 2 分 / 弱词 1 分），阈值也按此判
    """
    out = {}
    for label, rule in spec.items():
        if not isinstance(rule, dict):
            continue
        score = 0
        for kw in rule.get("keywords", []):
            if kw:
                score += body.count(kw)
        for pat in rule.get("patterns", []):
            try:
                score += len(re.findall(pat, body))
            except re.error:
                continue
        if dim == "关系":
            score = rel_score(body, label, score, rule.get("keywords", []))
            # 阈值按标签的「强词数量」定；min_override 供「标题匹配」等场景放宽
            need = min_override if min_override is not None else (
                3 if label in ("政敌", "同盟") else 4)
        else:
            need = auto_min(rule, floor)
        if score >= need:
            out[label] = score
    if len(out) > cap:
        order = SPECIFICITY.get(dim) or []
        rank = {t: i for i, t in enumerate(order)}
        out = dict(sorted(out.items(),
                          key=lambda kv: (rank.get(kv[0], len(order)), -kv[1]))[:cap])
    return out


# ------------------------------------------------------------ 单篇打标
def tag_one(rec, labels, matchers, dims, ov, contained=None):
    body = rec["body"]
    raw_kind = rec.get("kind") or rec["fm"].get("kind", "")
    kind = KIND_ALIAS.get(raw_kind, raw_kind)
    tags = []           # (label, dimension, weight)
    dim_owner = {}      # 非实体标签 → 维度列表（实体标签在 labels 里有维度）

    tags.append((kind, "文类", 1))
    for layer in layers_for(kind, body):
        tags.append((layer, "叙事层级", 1))
    tags.append((length_tag(len(body)), "篇幅", 1))

    # 实体 / 剧情线（**允许同一标签命中多个分面**，例如 长歌＝文类+剧情线）
    body_hits = longest_matches(body, matchers)
    for (label, dim), cnt in body_hits.items():
        tags.append((label, dim, cnt))

    # 包含关系补标（**只对登记过的别名**）：
    # 最长匹配会让「纠察队总部」吃掉同句里的「纠察队」，于是本该打上的上级标签
    # 反而丢了（hx-041 实测）。这里只补「确实被登记为别名」的包含关系，
    # 而不是任意子串——否则「中分山」会顺手补出「分山」这种不存在的东西。
    for (label, _dim), _c in list(body_hits.items()):
        for sub in contained.get(label, ()):
            for d in (labels.get(sub, {}).get("dimensions") or []):
                tags.append((sub, d, 1))

    # 标题专名：少数篇目的人名**只出现在标题里**——
    # 如《花絮：原绘自述史》通篇用「我」，《楔子：陆柩以前的故事》正文只出现简称。
    # 判定从严：只取**词表里已有的专名**，且该名在正文里确实没出现过。
    raw_title = rec.get("title") or rec["fm"].get("title", "")
    title = re.sub(r"^[^：:]{1,8}[：:]\s*", "", raw_title).strip()
    if title:
        seen_labels = {lbl for (lbl, _d) in body_hits}
        for (label, dim), _c in longest_matches(title, matchers).items():
            if len(label) < 2 or label in seen_labels:
                continue
            tags.append((label, dim, 1))

    # 标题里的**语义维度标签**（标题是最强的主题信号）：
    # 例如《花絮：高冒与高领之结束政敌的生物学生命》标题就写着「政敌」，
    # 但正文没有出现该词，纯正文匹配会漏掉。标题用更低阈值（2）——
    # 标题是全篇的概括，蹭到泛词的噪声远比正文小。
    if title:
        have = {t[0] for t in tags}
        for dim, spec in (("关系", dims.get("关系", {})),
                          ("事件类型", dims.get("事件类型", {})),
                          ("主题词", dims.get("主题词", {})),
                          ("时间", dims.get("时间", {}))):
            for label, score in dim_hits(title, spec, floor=1, dim=dim,
                                         min_override=2 if dim == "关系" else None).items():
                if label not in have:
                    tags.append((label, dim, score))

    # 合集 → 剧情线
    coll = rec.get("collection") or rec["fm"].get("collection", "")
    coll_norm = re.sub(r"[（(]未发布[)）]\s*", "", coll).strip()
    cs = (ov.get("剧情线收敛", {}) or {}).get("合集映射", {}) or {}
    for key in (coll, coll_norm):
        for s in cs.get(key, []):
            tags.append((s, "剧情线", 1))

    # 主题 / 事件 / 关系 / 基调 / 时间
    # 阈值（floor）按维度分别设；`auto_min()` 再按该标签的关键词条数缩放。
    # 2026-10-14 调整：作者要求放宽「关系」——它只有 5 个标签（恋人/政敌等被卡掉），
    # 属低频高信息量维度。放宽后由人工核实结果，故 floor 取下限。
    for dim, spec, floor in (("主题", dims.get("主题", {}), 4),
                             ("事件类型", dims.get("事件类型", {}), 3),
                             ("关系", dims.get("关系", {}), 2),
                             ("主题词", dims.get("主题词", {}), 3),
                             ("时间", dims.get("时间", {}), 1)):
        for label, score in dim_hits(body, spec, floor=floor, dim=dim).items():
            tags.append((label, dim, score))

    # 合并同一个标签的多个维度：dims 取并集、weight 取最大。
    # 注意：若该标签在词表里**声明**了多个维度（如 长歌＝文类+剧情线、背叛＝主题词+关系），
    # 即使本次只有其中一个维度的规则命中，也保留词表声明的全部维度——
    # 因为「重合分类」是标签的固有属性，不该随篇目波动。
    merged = {}         # label -> {"dims": [...], "w": int}
    for label, dim, w in tags:
        m = merged.setdefault(label, {"dims": [], "w": 0})
        if dim not in m["dims"]:
            m["dims"].append(dim)
        m["w"] = max(m["w"], w)
        for d in (labels.get(label, {}).get("dimensions") or []):
            if d not in m["dims"]:
                m["dims"].append(d)
    for label, m in merged.items():
        m["dims"].sort(key=lambda d: PRIORITY.get(d, 8))

    ordered = sorted(
        ((lab, m["dims"], m["w"]) for lab, m in merged.items()),
        key=lambda t: (min(PRIORITY.get(d, 8) for d in t[1]), -t[2], t[0]))

    ENTITY_DIMS = ("人物", "组织", "地理", "设施", "剧情线")
    primary = [t[0] for t in ordered if set(t[1]) & set(ENTITY_DIMS)][:3]
    if len(primary) < 3:      # 没有实体标签的篇目（如四格、纯论说），用主题补齐
        for t in ordered:
            if set(t[1]) & {"主题", "事件类型"} and t[0] not in primary:
                primary.append(t[0])
            if len(primary) >= 3:
                break
    return ordered, primary, dim_owner


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only-new", action="store_true", help="只重算 hash 变化的条目")
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()

    labels, matchers, entities, ov, contained = load_vocab()
    dims = load_dimensions()
    if not labels:
        sys.exit("词表为空：请先准备 data/vocab_people.json 与 data/vocab_entities.json")

    entries = common.load_entries()
    old = {}
    outp = os.path.join(DATA, "tags.json")
    if args.only_new and os.path.exists(outp):
        prev = json.load(open(outp, encoding="utf-8"))
        old = {e["id"]: e for e in prev.get("entries", [])}

    tag_index = collections.defaultdict(list)
    known_dims = {}
    entry_tags = []
    unchanged = 0
    for rec in entries:
        eid = rec["id"]
        if args.only_new and eid in old and old[eid].get("source_hash") == rec.get("source_hash"):
            entry_tags.append(old[eid])
            for t in old[eid]["tags"]:
                tag_index[t].append(eid)
                d = old[eid].get("dims", {}).get(t)
                known_dims.setdefault(t, d if isinstance(d, list) else ([d] if d else []))
            unchanged += 1
            continue
        ordered, primary, dim_owner = tag_one(rec, labels, matchers, dims, ov, contained)
        rec_out = {
            "id": eid,
            "title": rec["title"],
            "kind": rec["kind"],
            "collection": rec["collection"],
            "origin": rec["origin"],
            "chars": rec.get("chars", len(rec["body"])),
            "source_hash": rec.get("source_hash"),
            "tags": [t[0] for t in ordered],
            "primary": primary,
            "weights": {t[0]: t[2] for t in ordered},
            # dims: 标签 → 维度**列表**（多维度标签会出现多个）
            "dims": {t[0]: t[1] for t in ordered},
        }
        # ── 实体类标签的「标签↔文章」相关性等级（红/橙/蓝） ──
        # 乙方案：确定性公式，见 tools/grading.py。只给实体类算。
        g_grades = {}
        _body = rec["body"]
        _n = max(1, len(_body))
        _spk = common.speaker_counts(_body)
        _ents = sorted(((t, rec_out["weights"].get(t, 1)) for t in rec_out["tags"]
                        if grading_mod.is_entity(rec_out["dims"].get(t))),
                       key=lambda x: -x[1])
        _rank = {t: i + 1 for i, (t, _w) in enumerate(_ents)}
        for _t, _w in _ents:
            _ratio = _w / _n * 1000.0
            _sp = _spk.get(_t, 0) if "人物" in (rec_out["dims"].get(_t) or []) else 0
            g_grades[_t] = grading_mod.grade_of(_w, _ratio, _rank[_t], _sp)
        rec_out["grades"] = g_grades
        entry_tags.append(rec_out)
        for t in rec_out["tags"]:
            tag_index[t].append(eid)
            known_dims.setdefault(t, rec_out["dims"][t])

    # slug 分配（冲突时追加序号，稳定：按标签名排序分配）
    all_tags = sorted(tag_index.keys())
    slugs, used = {}, set()
    for t in all_tags:
        s = common.slugify(t)
        base, k = s, 1
        while s in used:
            k += 1
            s = "%s-%d" % (base, k)
        used.add(s)
        slugs[t] = s

    tag_meta = {}
    for t in all_tags:
        meta = labels.get(t, {})
        dims_list = list(meta.get("dimensions") or [])
        for d in (known_dims.get(t) or []):
            if d not in dims_list:
                dims_list.append(d)
        # 去掉空值，按展示顺序排序；多维度标签保留全部维度
        dims_list = [d for d in dims_list if d]
        if not dims_list:
            dims_list = ["未分类"]
        dim_order_all = ["文类", "叙事层级", "人物", "组织", "地理", "设施",
                         "剧情线", "主题", "事件类型", "关系", "主题词", "时间",
                         "篇幅", "未分类"]
        dims_list.sort(key=lambda d: dim_order_all.index(d) if d in dim_order_all else 99)
        tag_meta[t] = {
            "label": t,
            "slug": slugs[t],
            "dimensions": dims_list,
            # 主维度：列表第一个（用于兼容旧调用与页面着色）
            "dimension": dims_list[0],
            "multi": len(dims_list) > 1,
            "doc_freq": meta.get("doc_freq", len(tag_index[t])),
            "in_vocab": bool(meta) or t in known_dims,
        }
        if meta.get("variants"):
            tag_meta[t]["variants"] = meta["variants"]

    dim_order = ["文类", "叙事层级", "人物", "组织", "地理", "设施",
                 "剧情线", "主题", "事件类型", "关系", "主题词", "时间",
                 "篇幅", "未分类"]
    present = {d for m in tag_meta.values() for d in m["dimensions"]}
    multi_tags = sorted(t for t, m in tag_meta.items() if m["multi"])
    out = {
        "note": "由 tools/tag_entries.py 生成；标签聚合供客户端使用。"
                "标签可属多个维度（如 长歌＝文类+剧情线），见 tags[x].dimensions",
        "entry_count": len(entry_tags),
        "tag_count": len(all_tags),
        "tag_order": [d for d in dim_order if d in present] +
                     sorted(present - set(dim_order)),
        "multi_dimension_tags": multi_tags,
        "grade_rule": "tools/grading.py（乙方案：频次+占比+篇内排名+发言次数）",
        "grade_dist": dict(collections.Counter(
            g for e in entry_tags for g in (e.get("grades") or {}).values())),
        "tags": tag_meta,
        "entries": entry_tags,
        "tag_index": {t: sorted(v) for t, v in sorted(tag_index.items())},
    }
    common.write_json(outp, out)
    common.write_json(os.path.join(DATA, "slugs.json"),
                      {"note": "中文标签 → 英文 slug", "slugs": slugs})

    if args.report:
        rep = ["# 标签分布报告\n", "条目数 %d，标签数 %d\n" % (len(entry_tags), len(all_tags))]
        by_dim = collections.defaultdict(list)
        for t, m in tag_meta.items():
            for d in m["dimensions"]:
                by_dim[d].append((len(tag_index[t]), t, m["in_vocab"]))
        rep.append("\n## 按维度统计（多维度标签会在每个维度各计一次）\n")
        rep.append("| 维度 | 标签数 | 例子（篇数最多 8 个） |\n|---|---:|---|\n")
        for d in sorted(by_dim, key=lambda d: -len(by_dim[d])):
            lst = sorted(by_dim[d], reverse=True, key=lambda x: (x[0], x[1]))
            rep.append("| %s | %d | %s |\n" % (d, len(lst),
                       "、".join("%s(%d)" % (t, n) for n, t, _ in lst[:8])))
        rep.append("\n## 跨维度标签（同一标签属多个维度）：%d 个\n\n"
                   % len(out["multi_dimension_tags"]))
        for t in out["multi_dimension_tags"]:
            rep.append("- **%s**（%d 篇）：%s\n"
                       % (t, len(tag_index[t]), " + ".join(tag_meta[t]["dimensions"])))
        rep.append("\n## 每篇标签数分布\n")
        cnt = collections.Counter(len(e["tags"]) for e in entry_tags)
        for k in sorted(cnt):
            rep.append("- %d 个标签：%d 篇\n" % (k, cnt[k]))
        unmapped = [t for t, m in tag_meta.items() if not m["in_vocab"]]
        rep.append("\n## 词表外标签（需审核后并入词表）：%d 个\n\n" % len(unmapped))
        if unmapped:
            rep.append("　".join(sorted(unmapped)) + "\n")
        with open(os.path.join(DATA, "tag_report.md"), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("".join(rep))

    print(json.dumps({"entries": len(entry_tags), "tags": len(all_tags),
                      "unchanged": unchanged}, ensure_ascii=False))


def dims_dim_of(tag, dims):
    for d, spec in (dims or {}).items():
        if isinstance(spec, dict) and tag in spec:
            return d
    return "未分类"


if __name__ == "__main__":
    main()
