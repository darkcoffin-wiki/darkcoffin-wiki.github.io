"""Build the matching sheet: fragments needing titles x unclaimed site titles.

Also: for entries where both sides have a title but the KIND prefix differs,
list them so the site version can be adopted (rule 1).
"""
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

WIKI = r"E:\DSHwork\heijiu\wiki"
ents = json.load(open(os.path.join(WIKI, "data", "entries.json"), encoding="utf-8"))["entries"]
official = json.load(open(os.path.join(WIKI, "data", "site_titles.json"), encoding="utf-8"))["titles"]

VOCAB = r"(剧情花絮|特别内容|特别环节|四格漫画|四格|长歌|花絮|楔子|画外音)"


def norm(t):
    s = re.sub(r"^" + VOCAB + r"\s*[:：]\s*", "", t)     # drop kind prefix
    s = s.replace("*", "")
    s = re.sub(r"[\s\u3000]", "", s)
    s = re.sub(r"[（）()【】\[\]「」『』“”\"'‘’、，,。.！!？?：:]", "", s)
    s = s.replace("——", "").replace("—", "").replace("-", "")
    return s


def kind_of(t):
    m = re.match(r"^\s*" + VOCAB, t)
    return m.group(1) if m else "?"


md_norm = {}
for e in ents:
    md_norm.setdefault(norm(e["title"]), []).append(e)

matched_ids, kind_diffs, missing_site = set(), [], []
for t in official:
    k = norm(t)
    if k in md_norm:
        hit = md_norm[k][0]
        matched_ids.add(hit["id"])
        if kind_of(t) != hit["kind"]:
            kind_diffs.append((t, kind_of(t), hit))
    else:
        missing_site.append(t)

print(f"official {len(official)}  matched {len(matched_ids)}  unmatched {len(missing_site)}")
print(f"kind-prefix differences (site wins): {len(kind_diffs)}")
for t, kd, e in kind_diffs:
    print(f"   {e['id']}  md:{e['kind']:<5} vs site:{kd:<5}  {t}")
    print(f"        md 标题: {e['title']}")

print("\n" + "=" * 78)
print("UNMATCHED SITE TITLES (candidate pool for the fragments)")
for t in missing_site:
    print(f"   {t}")

# fragments needing a title = auto-titled entries
need = [e for e in ents if e["title_source"] == "auto"]
print(f"\n" + "=" * 78)
print(f"FRAGMENTS NEEDING A TITLE: {len(need)}")
for e in need:
    print(f"   {e['id']}  {e['chars']:>5}字  {e['kind']:<4} {e['title'][:66]}")

# also: entries whose md title has no site counterpart at all
extra = [e for e in ents if e["id"] not in matched_ids]
print(f"\nentries with NO site counterpart: {len(extra)}")
for e in extra:
    tag = "AUTO" if e["title_source"] == "auto" else "    "
    print(f"   {tag} {e['id']}  {e['chars']:>5}字 {e['kind']:<5} {e['title'][:62]}")

json.dump({"unmatched_site_titles": missing_site,
           "kind_differences": [{"site": t, "site_kind": kd, "md_id": e["id"],
                                 "md_title": e["title"], "md_kind": e["kind"]}
                                for t, kd, e in kind_diffs],
           "need_title": [{"id": e["id"], "chars": e["chars"], "kind": e["kind"],
                           "title": e["title"], "line": e["source_line"]} for e in need],
           "no_site_counterpart": [{"id": e["id"], "kind": e["kind"], "chars": e["chars"],
                                    "title": e["title"], "auto": e["title_source"] == "auto"}
                                   for e in extra]},
          open(os.path.join(WIKI, "data", "match_sheet.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\nwrote data/match_sheet.json")
