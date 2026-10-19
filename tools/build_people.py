"""生成两张人物表（脱敏后）供黑柩问答查「别名 / 最早出现 / 出场次数 / 玩家用名」。

来源
  E:\\黑柩\\黑柩跑团记录-整理\\场次志\\黑柩NPC总表.md        （379 人，无 QQ）
  E:\\黑柩\\黑柩跑团记录-整理\\附录C-玩家用名总表.md          （37 人，**含 QQ 列，必须删**）

输出
  docs/records/npc.md       NPC 总表（原样，若确认无账号）
  docs/records/players.md   玩家用名（删除 QQ 列）

用法
  python tools/build_people.py [--force]
"""
import argparse
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

W = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_NPC = r"E:\黑柩\黑柩跑团记录-整理\场次志\黑柩NPC总表.md"
SRC_PLY = r"E:\黑柩\黑柩跑团记录-整理\附录C-玩家用名总表.md"
OUT = os.path.join(W, "docs", "records")

NUM_RE = re.compile(r"(?<!\d)\d{5,12}(?!\d)")


def find_accounts(text):
    """返回文本里所有 5~12 位独立数字（疑似账号）。"""
    return sorted(set(NUM_RE.findall(text)))


def scrub_line(line, accounts):
    for a in accounts:
        line = line.replace(a, "[已隐去]")
    return line


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    # ── NPC 总表 ──
    if not os.path.exists(SRC_NPC):
        sys.exit("找不到 NPC 总表：%s" % SRC_NPC)
    npc = io.open(SRC_NPC, encoding="utf-8").read()
    npc_acc = find_accounts(npc)
    print("NPC 总表：%d 字，疑似账号 %d 个 %s"
          % (len(npc), len(npc_acc), npc_acc[:5] if npc_acc else ""))
    if npc_acc:
        npc = "\n".join(scrub_line(l, npc_acc) for l in npc.split("\n"))
        print("   已替换为 [已隐去]")

    # 加一句给问答用的说明头
    header = (
        "<!-- 供黑柩问答检索：NPC 总表（379 人）。"
        "字段：NPC / 别名·异写 / 身份职务 / 阵营所属 / 首见季 / 出场次数 / 描述。"
        "「别名·异写」为空写「未明」。作者已声明会「吃书」，前后不一一律照录。-->\n"
    )
    data = (header + npc).encode("utf-8")
    p = os.path.join(OUT, "npc.md")
    old = open(p, "rb").read() if os.path.exists(p) else None
    if old != data:
        open(p, "wb").write(data)
        print("   写出 npc.md（%.0f KB）" % (len(data) / 1024))
    else:
        print("   npc.md 无变化")

    # ── 玩家用名总表：删掉 QQ 列 ──
    if not os.path.exists(SRC_PLY):
        sys.exit("找不到玩家用名总表：%s" % SRC_PLY)
    raw = io.open(SRC_PLY, encoding="utf-8").read()

    # ① 先从 QQ 列收集「真正的账号」，后面只替换这些
    #    不能把所有 5~12 位数字都替换——「千分」的群名片之一就叫「1000000」，
    #    那是昵称不是账号，替换掉会丢信息。
    qq_col = set()
    for ln in raw.split("\n"):
        if not ln.startswith("|"):
            continue
        cells = ln.split("|")
        if len(cells) >= 8:
            v = cells[3].strip().strip("`").strip()
            if v and v != "QQ" and not set(v) <= set("-—:"):
                qq_col.add(v)
    print("玩家用名总表：QQ 列 %d 个账号" % len(qq_col))

    # ② 删掉第 3 个数据单元格（QQ），**表头与分隔行一起删**，
    #    否则表头 6 列、数据 5 列，表格会错位。
    kept, dropped = [], 0
    for ln in raw.split("\n"):
        if ln.startswith("|"):
            cells = ln.split("|")
            if len(cells) >= 8:
                del cells[3]
                ln = "|".join(cells)
                dropped += 1
        kept.append(ln)
    ply = "\n".join(kept)
    # 说明文字里不必再出现「QQ」字样
    ply = ply.replace("该 QQ 用过的", "该玩家用过的")
    ply = ply.replace("QQ 号", "账号")

    # ③ 只在其它列里替换「确认属于 QQ 列」的号码
    hits = 0
    if qq_col:
        out_lines = []
        for ln in ply.split("\n"):
            for a in qq_col:
                if a in ln:
                    ln = ln.replace(a, "[已隐去]")
                    hits += 1
            out_lines.append(ln)
        ply = "\n".join(out_lines)
    print("   删除 QQ 列 %d 行（含表头）｜ 其它列替换账号 %d 处" % (dropped, hits))

    pheader = (
        "<!-- 供黑柩问答检索：玩家用名总表（37 人）。"
        "已删除账号列。字段：玩家 / 用过的名字（全部） / 总计条数 / 实场数。"
        "同一玩家在不同季可能换角色名，这是原作写法不是笔误。-->\n"
    )
    data = (pheader + ply).encode("utf-8")
    p = os.path.join(OUT, "players.md")
    old = open(p, "rb").read() if os.path.exists(p) else None
    if old != data:
        open(p, "wb").write(data)
        print("   写出 players.md（%.0f KB）" % (len(data) / 1024))
    else:
        print("   players.md 无变化")


if __name__ == "__main__":
    main()
