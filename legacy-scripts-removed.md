# 已删除的根目录早期脚本（2026-10-16）

这些是开发早期的一次性调试/试验脚本，已被 `tools/` 下的正式解析器与生成器取代。
如需找回：`git log --diff-filter=D --name-only` 或 `git show <旧commit>:<文件名>`。

- `align_277.py`（2.7 KB）
- `build_v5.py`（7.0 KB）
- `build_v6.py`（11.1 KB）
- `build_vocab.py`（3.5 KB）
- `build_vocab2.py`（4.6 KB）
- `check_consolidated_docx.py`（2.3 KB）
- `confirm_docx_rule.py`（3.8 KB）
- `debug_miss.py`（1.2 KB）
- `diagnose_empty.py`（2.7 KB）
- `extract_long.py`（7.0 KB）
- `final_review.py`（3.7 KB）
- `fix_last.py`（0.7 KB）
- `fix_path.py`（0.9 KB）
- `fix_review.py`（4.3 KB）
- `fix_rule.py`（2.4 KB）
- `inspect_early_docx.py`（1.6 KB）
- `inspect_zero.py`（1.5 KB）
- `locate_fragments.py`（2.1 KB）
- `make_matching_card.py`（3.4 KB）
- `make_matching_card2.py`（3.3 KB）
- `match_autos.py`（2.2 KB）
- `match_autos2.py`（1.6 KB）
- `match_autos3.py`（1.7 KB）
- `match_sheet.py`（3.3 KB）
- `merge_corpus.py`（6.1 KB）
- `mine_names.py`（2.7 KB）
- `parse_277_site.py`（2.6 KB）
- `parse_huaxu.py`（6.2 KB）
- `parse_site_all.py`（4.1 KB）
- `parse_v3.py`（6.0 KB）
- `parse_v4.py`（6.5 KB）
- `patch_v6.py`（2.1 KB）
- `positional_check.py`（2.1 KB）
- `probe_big.py`（2.1 KB）
- `probe_hash.py`（1.8 KB）
- `probe_largest.py`（2.3 KB）
- `probe_site_structure.py`（3.7 KB）
- `qa_final.py`（2.2 KB）
- `rebuild_review.py`（3.8 KB）
- `reconcile.py`（3.3 KB）
- `reconcile2.py`（3.3 KB）
- `refresh_spec.py`（4.9 KB）
- `report_split.py`（1.3 KB）
- `scan_docx_sources.py`（4.0 KB）
- `scrape_site.py`（2.9 KB）
- `scrape_toc.py`（2.9 KB）
- `site_split.py`（2.7 KB）
- `site_vs_docx.py`（5.2 KB）
- `verify_277_map.py`（2.5 KB）
- `verify_parse.py`（2.0 KB）
- `verify_v4.py`（2.4 KB）
- `why_missing.py`（1.2 KB）

---

## 同时删除的早期目录（2026-10-16）

这三个目录是早期「抓站点 → 抽文本 → 切条目」流水线的产物，
内容均已落在 `source/` 里（已逐项核实覆盖）：

### `_review_long/`（5 个文件 / 378 KB）

超长条目（>15000 字）检查单。4 篇均已在 `source/`：`hx-180`、`hx-150`、`hx-206`、`hx-200`。

- `_索引.md`
- `long-01-62972字-花絮：黑帮的宽恕，侠客的利刃之下.md`
- `long-02-25064字-楔子：蚀血教来袭？这是什么.md`
- `long-03-22271字-楔子：赫炎的审讯，北沙内乱的暗流.md`
- `long-04-20964字-画外音：极恶之人，在农田赎罪一生.md`

### `_site_raw/`（11 个文件 / 3946 KB）

11 篇站点文章的原始 HTML 快照（原先用于离线提取，不再需要联网）。

- `1015.html`
- `264.html`
- `277.html`
- `289.html`
- `476.html`
- `484.html`
- `494.html`
- `535.html`
- `592.html`
- `737.html`
- `850.html`

### `_site_text/`（11 个文件 / 1770 KB）

从上述 HTML 抽出的纯文本（11 个「总集篇」）。内容已拆分进 `source/` 的 212 个条目文件。

- `北沙篇花絮总集篇.md`
- `北沙篇花絮总集篇二.md`
- `总集篇一.md`
- `总集篇七.md`
- `总集篇三.md`
- `总集篇二.md`
- `总集篇五.md`
- `总集篇八.md`
- `总集篇六.md`
- `总集篇四.md`
- `长歌总集篇一.md`

