#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""标签 ↔ 文章 相关性分级（乙方案：确定性公式，零模型调用）。

作者 2026-10-14 定的口径
------------------------
* 三个等级：**红 > 橙 > 蓝**（红＝相关性最高）
* **只给实体类标签分级**（人物 / 组织 / 地理 / 设施 / 剧情线）
* 等级要影响排序：标签页里文章按相关性降序；分类页、首页同理
* 不做跨篇一致性处理（那属于以后的模型方案）

判据（按 红 → 橙 顺序判，都不满足即蓝）
--------------------------------------
用四个信号，兼顾长短篇：

* `freq`   该标签在本篇出现次数
* `ratio`  每千字出现次数（消除篇幅差异）
* `rank`   该标签在本篇**实体类**里按 freq 的排名
* `speak`  该标签作为**对白发言人**的次数（`名字：`），戏份强信号

| 等级 | 满足任一条 |
|---|---|
| 红 | `rank==1 且 freq>=10`；`freq>=12`；`speak>=15`；`ratio>=8` |
| 橙 | `rank<=3 且 freq>=3`；`freq>=5`；`speak>=6`；`ratio>=3` |

导出：
    grade_of(freq, ratio, rank, speak) -> "红" | "橙" | "蓝"
    GRADE_ORDER = {"红": 0, "橙": 1, "蓝": 2}
"""
import re

ENTITY_DIMS = ("人物", "组织", "地理", "设施", "剧情线")
GRADES = ("红", "橙", "蓝")
GRADE_ORDER = {"红": 0, "橙": 1, "蓝": 2}
GRADE_COLOR = {"红": "#c8553d", "橙": "#d98b2b", "蓝": "#4f7d9d"}


def is_entity(dims):
    return bool(set(dims or ()) & set(ENTITY_DIMS))


def speaker_hits(body, tag):
    """该标签作为对白发言人出现的次数。"""
    if not body or not tag:
        return 0
    pat = re.compile(r"(?:^|\n)\s*(?:\*\*)?%s(?:\*\*)?\s*[：:]" % re.escape(tag))
    return len(pat.findall(body))


def grade_of(freq, ratio, rank, speak):
    """按判据给单对（标签, 文章）定级。参数全部为该对在本篇内的统计量。"""
    # 红
    if (rank == 1 and freq >= 10) or freq >= 12 or speak >= 15 or ratio >= 8:
        return "红"
    # 橙
    if (rank <= 3 and freq >= 3) or freq >= 5 or speak >= 6 or ratio >= 3:
        return "橙"
    return "蓝"


def grades_dist(rows):
    """统计用：rows 为 dict 序列，每项含 grade 字段。"""
    import collections
    return collections.Counter(r["grade"] for r in rows)
