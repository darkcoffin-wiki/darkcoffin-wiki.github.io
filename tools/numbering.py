#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分层序号：把标题层级编号集中在这里（渲染与解析共用）。

作者 2026-10-14 要求：**所有标题都用分层序号标示层级**。

编号方案
--------
* 第 1 层：`一、` `二、` … `十二、`          （季志的十节 / 场次卡的十二字段）
* 第 2 层：`（一）` `（二）` …               （季摘要小节 / 剧情摘要小节）
* 第 3 层：`1.` `2.` …                       （必要时再细分）
* 第 4 层：`(1)` `(2)` …                     （极少用到）

设计要点
--------
* 编号由**数据生成**，不写死在原文里 —— 原文保持干净，改动只影响渲染
* 中文数字只用于 1~2 层（超过 20 项的第 2 层用阿拉伯数字，避免「（二十一）」过长）
* 若小节名**已经**以同样的序号开头（如 `一、本季概览`），不重复添加
"""
import re

CN = "零一二三四五六七八九"


def cn_num(n):
    """阿拉伯数字 → 中文数字（支持到 99）。3→三、10→十、11→十一、21→二十一。"""
    if n < 0:
        return str(n)
    if n < 10:
        return CN[n]
    if n == 10:
        return "十"
    if n < 20:
        return "十" + CN[n % 10]
    if n % 10 == 0:
        return CN[n // 10] + "十"
    return CN[n // 10] + "十" + CN[n % 10]


def level1(i):
    """第 1 层：一、二、…"""
    return "%s、" % cn_num(i)


def level2(i):
    """第 2 层：（一）（二）…；超过 20 项改用 (21) 这种紧凑写法。"""
    if i <= 20:
        return "（%s）" % cn_num(i)
    return "(%d) " % i


def level3(i):
    return "%d. " % i


def level4(i):
    return "(%d) " % i


NUM_PREFIX = re.compile(
    r"^\s*(?:[一二三四五六七八九十]+[、.．]|（[一二三四五六七八九十]+）"
    r"|\(\d+\)\s*|\d+\.\s*)\s*")


def has_number(title):
    """标题是否已经自带序号（避免重复加）。"""
    return bool(NUM_PREFIX.match(title or ""))


TAIL_PAGE = re.compile(r"\s{0,3}(\d{1,3})\s*$")


# 允许出现在页码之前的收尾字符：各类右括号与中英文引号（汉字用区间单独判断）
TAIL_OK = "）)》」』”\"”\"'’"


def _ok_tail(ch):
    return ch in TAIL_OK or "\u4e00" <= ch <= "\u9fff"


def strip_number(title, max_page=9999):
    """去掉已有的序号前缀与**尾随页码**，得到纯名字。

    必须剥页码：设定集标题带页码（`一、这部书的来源25`、`TRPG机制与“穿越者”30`），
    否则会误判成「没有编号」而再加一遍 → `一、一、这部书的来源`。

    max_page：只有 ≤ 该值的数字才当作页码，避免误伤名字里的数字（如「0083号计划」）。
    """
    t = (title or "").strip()
    t = NUM_PREFIX.sub("", t).strip()
    m = TAIL_PAGE.search(t)
    if m:
        head = t[:m.start()].rstrip()
        if head and _ok_tail(head[-1]) and int(m.group(1)) <= max_page:
            t = head
    return t


def number_items(items, key="title", out_key="no", level=1):
    """给一串带 `title` 的 dict 就地加序号。

    返回带编号的 list；同时写入：
      * `no`       —— 编号文本，如 `一、` / `（三）`
      * `numbered` —— 编号 + 原名，如 `一、本季概览`
      * `pure`     —— 去掉序号的原名，如 `本季概览`（供锚点/查找）
    """
    fn = {1: level1, 2: level2, 3: level3, 4: level4}.get(level, level1)
    done = []
    for i, it in enumerate(items, 1):
        name = strip_number(it.get(key, ""))
        rec = dict(it)
        rec["pure"] = name
        rec["no"] = fn(i)
        rec["numbered"] = fn(i) + name
        rec["level"] = level
        done.append(rec)
    return done


def number_sections(sections, level=1):
    """给 `{标题: 正文}` 形态的分节加序号。

    返回 [(序号, 纯名, 编号后标题, 正文)]，顺序保持原样。
    """
    fn = {1: level1, 2: level2, 3: level3, 4: level4}.get(level, level1)
    out = []
    for i, (title, body) in enumerate(sections.items(), 1):
        pure = strip_number(title)
        out.append((fn(i), pure, fn(i) + pure, body))
    return out
