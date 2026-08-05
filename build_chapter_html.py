#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 chapters/*.md 生成 index.html 里的章节 HTML，并校验两者是否同步。

本仓库同一份章节内容存在于四处（见 CLAUDE.md），其中"章节 markdown → index.html
的章节 HTML"这一步原先靠手工维护，是最容易漏改的一环。本脚本把它变成可执行、
可校验的：

    python3 build_chapter_html.py --check       # 全部章节比对，不一致则 exit 1
    python3 build_chapter_html.py --check ch4   # 只比对第 4 章
    python3 build_chapter_html.py --write ch4   # 用 markdown 重新生成第 4 章 HTML
    python3 build_chapter_html.py --diff ch4    # 打印差异，不写文件

改完章节 markdown 的标准流程：
    --write chN  →  build_search_index.py  →  两个 --check 都通过

## 生成约定（对齐 index.html 中 ch1–ch13 的既有写法）

- 每个 `<section id="chN">` 的开头（ch-label / h1 / minitoc）是**手工维护**的，
  本脚本不碰；只重新生成 `</details>` 之后的正文。
- `##` → `<h2>`；`###` → `<h3 id="chN-sM">`（M 按章内出现顺序，minitoc 靠它跳转）；
  `####` → `<h4>`；`#####` → `<h5>`。
- 行内强调按 **CommonMark 的 left/right-flanking 规则**判定。中文正文里
  `一段**"上下文"前缀**再嵌入` 这类写法，开分隔符后紧跟标点而前面是汉字，
  CommonMark 判定为不可开启、原样输出 `**`——朴素正则会错误加粗。
- **不做**裸 URL 自动链接：只有 markdown 的 `[文字](url)` 才会变成 `<a>`。
  这与既有 HTML 一致（ch4 的 21 个裸 URL 在 md 与 HTML 里都是裸的）。
- 转义 `& < > "`，保留裸单引号——同样是既有 HTML 的口径。

## 已知偏差（脚本会报告，但不擅自改写）

ch0 与 ch14 的现有 HTML 不符合上述约定：标题层级整体高一级，且 `<h3>` 缺少
`id="chN-sM"`——ch14 的本章导航六个链接因此全部指向不存在的锚点。用
`--write ch14` 可将其规范化（会改变这一章的渲染层级，属有意为之的修复）。
"""

# macOS 自带的 python3 是 3.9，不认 PEP 604 的 `str | None` 注解。CLAUDE.md 与
# README 里的命令都写 `python3 build_chapter_html.py`，没有这一行，只装了系统
# Python 的机器上克隆下来就跑不了同步脚本（TypeError: unsupported operand |）。
from __future__ import annotations

import argparse
import pathlib
import re
import sys
import unicodedata

REPO = pathlib.Path(__file__).resolve().parent
INDEX = REPO / "index.html"
CHAPTERS = REPO / "chapters"


# ── 行内 ────────────────────────────────────────────────────────────────

def esc(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
                .replace(">", "&gt;").replace('"', "&quot;"))


def _is_punct(ch: str) -> bool:
    return bool(ch) and unicodedata.category(ch).startswith(("P", "S"))


def _is_space(ch: str) -> bool:
    return ch == "" or ch.isspace()


def _emphasis(text: str, marker: str, tag: str) -> str:
    """按 CommonMark 的 flanking 规则配对强调分隔符。"""
    n, m = len(text), len(marker)
    runs, i = [], 0
    while i <= n - m:
        if text[i:i + m] != marker:
            i += 1
            continue
        prev = text[i - 1] if i else ""
        nxt = text[i + m] if i + m < n else ""
        # 单星号这一趟不拆开未配对的 ** 连排（CommonMark 按游程处理）
        if m == 1 and (prev == "*" or nxt == "*"):
            i += 1
            continue
        left = (not _is_space(nxt)) and (
            not _is_punct(nxt) or _is_space(prev) or _is_punct(prev))
        right = (not _is_space(prev)) and (
            not _is_punct(prev) or _is_space(nxt) or _is_punct(nxt))
        runs.append((i, left, right))
        i += m

    used, open_idx = set(), None
    for idx, (pos, left, right) in enumerate(runs):
        if open_idx is None:
            if left:
                open_idx = idx
        elif right and pos > runs[open_idx][0] + m:
            used.update({runs[open_idx][0], pos})
            open_idx = None
        elif left and not right:
            open_idx = idx

    out, i, depth = [], 0, 0
    while i < n:
        if i in used:
            out.append(f"<{tag}>" if depth == 0 else f"</{tag}>")
            depth ^= 1
            i += m
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def inline(text: str) -> str:
    """行内转换：代码跨度与链接先占位，再在**整串**上配对强调。

    占位而非切段，是因为强调可以跨越代码跨度成对出现——
    `**A `code` B**` 的两个 `**` 若被代码跨度切进不同片段，就永远配不上对。
    """
    slots: list[str] = []

    def stash(rendered: str) -> str:
        slots.append(rendered)
        # 用 CJK 私有区字符占位：不是标点也不是空白，不会扰动 flanking 判定
        return "" + str(len(slots) - 1) + ""

    def take_code(m):
        return stash(f"<code>{esc(m.group(1))}</code>")

    def take_link(m):
        label = _emphasis(esc(m.group(1)), "**", "strong")
        return stash(f'<a href="{esc(m.group(2))}">{label}</a>')

    text = re.sub(r"`([^`]+)`", take_code, text)
    text = LINK_RE.sub(take_link, text)
    text = _emphasis(esc(text), "**", "strong")
    text = _emphasis(text, "*", "em")
    return re.sub(r"(\d+)", lambda m: slots[int(m.group(1))], text)


# ── 块级 ────────────────────────────────────────────────────────────────

BULLET_RE = re.compile(r"^([-*+])(\s+)(.*)$")
ORDERED_RE = re.compile(r"^(\d+)\.(\s+)(.*)$")
TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|$")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _item_match(line: str):
    s = line.lstrip(" ")
    m = BULLET_RE.match(s)
    if m:
        return "ul", m.group(3)
    m = ORDERED_RE.match(s)
    if m:
        return "ol", m.group(3)
    return None


class Renderer:
    def __init__(self, chapter_id: str | None = None) -> None:
        self.chapter_id = chapter_id
        self.h3_count = 0
        self.out: list[str] = []

    # 块序列 → HTML
    def render(self, md: str) -> str:
        self.out = []
        self.h3_count = 0
        self._blocks(md.split("\n"), 0)
        return "\n".join(self.out)

    def _blocks(self, lines: list[str], base_indent: int) -> None:
        i, n = 0, len(lines)
        while i < n:
            line = lines[i]
            if not line.strip():
                i += 1
                continue
            stripped = line.strip()

            if stripped.startswith("```"):
                i = self._code_fence(lines, i)
                continue
            if re.fullmatch(r"[-*_]{3,}", stripped):
                self.out.append("<hr />")
                i += 1
                continue
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                self._heading(len(m.group(1)), m.group(2))
                i += 1
                continue
            if stripped.startswith(">"):
                i = self._blockquote(lines, i)
                continue
            if stripped.startswith("|") and i + 1 < n and TABLE_SEP_RE.match(lines[i + 1].strip()):
                i = self._table(lines, i)
                continue
            if _item_match(line):
                i = self._list(lines, i, base_indent)
                continue
            i = self._paragraph(lines, i)

    def _heading(self, level: int, text: str) -> None:
        if level == 3 and self.chapter_id:
            self.h3_count += 1
            anchor = f' id="{self.chapter_id}-s{self.h3_count}"'
        else:
            anchor = ""
        self.out.append(f"<h{level}{anchor}>{inline(text)}</h{level}>")

    def _code_fence(self, lines: list[str], i: int) -> int:
        info = lines[i].strip().lstrip("`").strip()
        i += 1
        body = []
        while i < len(lines) and not lines[i].strip().startswith("```"):
            body.append(lines[i])
            i += 1
        cls = f' class="language-{esc(info)}"' if info else ""
        self.out.append(f"<pre><code{cls}>" + esc("\n".join(body)) + "\n</code></pre>")
        return i + 1

    def _blockquote(self, lines: list[str], i: int) -> int:
        """引用块内部按块递归渲染——引用里可以有列表、多段落。"""
        body = []
        while i < len(lines) and lines[i].strip().startswith(">"):
            body.append(re.sub(r"^>\s?", "", lines[i]))
            i += 1
        self.out.append("<blockquote>")
        sub = Renderer(self.chapter_id)
        sub.h3_count = self.h3_count
        sub._blocks(body, 0)
        self.out += sub.out
        self.h3_count = sub.h3_count
        self.out.append("</blockquote>")
        return i

    def _table(self, lines: list[str], i: int) -> int:
        def cells(row: str) -> list[str]:
            return [c.strip() for c in row.strip().strip("|").split("|")]

        header = cells(lines[i])
        i += 2
        self.out += ["<table>", "<thead>", "<tr>"]
        self.out += [f"<th>{inline(c)}</th>" for c in header]
        self.out += ["</tr>", "</thead>", "<tbody>"]
        while i < len(lines) and lines[i].strip().startswith("|"):
            self.out.append("<tr>")
            self.out += [f"<td>{inline(c)}</td>" for c in cells(lines[i])]
            self.out.append("</tr>")
            i += 1
        self.out += ["</tbody>", "</table>"]
        return i

    def _paragraph(self, lines: list[str], i: int) -> int:
        body = [lines[i].strip()]
        i += 1
        while i < len(lines) and lines[i].strip() and not _item_match(lines[i]):
            s = lines[i].strip()
            if (s.startswith(("```", ">", "#", "|"))
                    or re.fullmatch(r"[-*_]{3,}", s)):
                break
            body.append(s)
            i += 1
        self.out.append(f"<p>{inline(chr(10).join(body))}</p>")
        return i

    # ── 列表：按缩进递归，区分 tight / loose ────────────────────────────
    def _list(self, lines: list[str], i: int, base_indent: int) -> int:
        tag = _item_match(lines[i])[0]
        indent = _indent(lines[i])
        items: list[list[str]] = []     # 每项的原始行（已去掉本层缩进）
        loose = False
        n = len(lines)

        while i < n:
            line = lines[i]
            if not line.strip():
                # 空行：若后面还接着本层的项/续行，则该列表为 loose
                j = i + 1
                while j < n and not lines[j].strip():
                    j += 1
                if j < n and _indent(lines[j]) >= indent and (
                        _item_match(lines[j]) or _indent(lines[j]) > indent):
                    if items:
                        loose = True
                        items[-1].append("")
                    i = j
                    continue
                break
            cur = _indent(line)
            if cur == indent and _item_match(line):
                if _item_match(line)[0] != tag:
                    break
                items.append([line.lstrip(" ")])
            elif items and cur >= indent:
                # 续行或子列表：剥掉本层缩进后交给递归（CommonMark 惰性续行）
                items[-1].append(line[indent:] if cur > indent else line)
            else:
                break
            i += 1

        while items and items[-1] and not items[-1][-1].strip():
            items[-1].pop()

        self.out.append(f"<{tag}>")
        for item in items:
            self._render_item(item, loose)
        self.out.append(f"</{tag}>")
        return i

    def _render_item(self, item_lines: list[str], loose: bool) -> None:
        head = _item_match(item_lines[0])[1]
        rest = item_lines[1:]
        # 首段 = head + 其后紧邻的续行（未被空行隔开、且不是子列表项）
        cont, k = [], 0
        while k < len(rest):
            s = rest[k].strip()
            if not s or _item_match(rest[k]) or s.startswith(("```", ">", "#", "|")):
                break
            cont.append(s)
            k += 1
        lead = inline("\n".join([head] + cont)) if head or cont else ""
        tail = rest[k:]

        if not tail:
            if loose:
                self.out.append("<li>")
                self.out.append(f"<p>{lead}</p>")
                self.out.append("</li>")
            else:
                self.out.append(f"<li>{lead}</li>")
            return

        # 有子块：先出首段，再递归渲染剩余内容
        self.out.append("<li>" + (f"\n<p>{lead}</p>" if loose else lead))
        sub = Renderer(self.chapter_id)
        sub.h3_count = self.h3_count
        dedent = min((_indent(l) for l in tail if l.strip()), default=0)
        sub._blocks([l[dedent:] if l.strip() else "" for l in tail], 0)
        self.out += sub.out
        self.h3_count = sub.h3_count
        self.out.append("</li>")


def convert(md: str, chapter_id: str | None = None) -> str:
    return Renderer(chapter_id).render(md)


# ── 内容体检 ────────────────────────────────────────────────────────────

BOLD_SPAN_RE = re.compile(r"\*\*([^*\n]+)\*\*")


def lint_bold(md: str) -> list[tuple[int, str]]:
    """找出"作者本意加粗、但标准 markdown 不会渲染"的片段。

    成因是 CommonMark 的 flanking 规则：`**原子命题（proposition）**再索引` 中，
    收尾的 `**` 前是全角括号（标点）、后是汉字（字母），不构成 right-flanking，
    于是整段原样输出 `**`。这类写法在 GitHub、笔记软件里都会露出星号。
    修法：把标点移出加粗范围，或在 `**` 后补一个空格。
    """
    bad = []
    for lineno, line in enumerate(md.split("\n"), 1):
        if "**" not in line:
            continue
        rendered = _emphasis(esc(line), "**", "strong")
        for m in BOLD_SPAN_RE.finditer(line):
            marked = f"<strong>{esc(m.group(1))}</strong>"
            if marked not in rendered:
                bad.append((lineno, m.group(0)))
    return bad


# ── index.html 读写 ─────────────────────────────────────────────────────

def chapter_files() -> dict[str, pathlib.Path]:
    """chN → chapters/NN-*.md（00-开篇导读 对应 ch0）。"""
    mapping = {}
    for p in sorted(CHAPTERS.glob("*.md")):
        num = int(p.name.split("-", 1)[0])
        mapping[f"ch{num}"] = p
    return mapping


def section_bounds(html: str, chapter_id: str) -> tuple[int, int]:
    ids = re.findall(r'<section id="([^"]+)"', html)
    idx = ids.index(chapter_id)
    start = html.index(f'<section id="{chapter_id}"')
    if idx + 1 < len(ids):
        end = html.index(f'<section id="{ids[idx + 1]}"')
    else:
        end = html.index("</section>", start) + len("</section>")
    return start, end


def split_section(block: str) -> tuple[str, str]:
    """把章节块拆成「手工维护的头部」与「生成的正文」。

    常规章节的头部到 `</details>`（本章导航）为止；ch0（开篇导读）没有导航，
    头部只有 `<div class="ch-label">`。
    """
    for marker in ("</details>", "</div>"):
        if marker in block:
            cut = block.index(marker) + len(marker)
            return block[:cut], block[cut:]
    raise ValueError("无法定位章节头部与正文的分界")


def wants_anchors(head: str) -> bool:
    """只有带本章导航的章节才需要 `id="chN-sM"` 锚点——导航正是靠它跳转。"""
    return "minitoc" in head


# 正文里含"只存在于网站、markdown 侧无对应源"的手工内容的章节。
# 这类章节不能用 --write 覆盖，否则手工内容会被 markdown 的降级说明顶掉。
MANUAL_CHAPTERS = {
    "ch13": '含手工维护的交互式分层图（<div id="hviz">），markdown 侧只有降级说明',
}


def existing_body(html: str, chapter_id: str) -> str:
    start, end = section_bounds(html, chapter_id)
    _, body = split_section(html[start:end])
    return body.strip("\n").removesuffix("</section>").rstrip("\n")


def generated_body(chapter_id: str, md_path: pathlib.Path, html: str) -> str:
    md = md_path.read_text(encoding="utf-8")
    # 首行 "# 第 N 章 · 标题" 由 h1/minitoc 手工承载，不参与生成
    body_md = md.split("\n", 1)[1] if md.startswith("# ") else md
    start, end = section_bounds(html, chapter_id)
    head, _ = split_section(html[start:end])
    return convert(body_md.lstrip("\n"), chapter_id if wants_anchors(head) else None)


def write_chapter(chapter_id: str, md_path: pathlib.Path) -> bool:
    html = INDEX.read_text(encoding="utf-8")
    start, end = section_bounds(html, chapter_id)
    block = html[start:end]
    head, _ = split_section(block)
    new_block = head + "\n" + generated_body(chapter_id, md_path, html) + "\n</section>\n"
    if new_block == block:
        return False
    INDEX.write_text(html[:start] + new_block + html[end:], encoding="utf-8")
    return True


# ── CLI ────────────────────────────────────────────────────────────────

TAG_RE = re.compile(r"<[^>]+>")


def text_of(html_fragment: str) -> str:
    """去标签 + 归一空白，用于"内容是否同步"的比对。

    默认用内容口径而非逐字节，是因为 index.html 的既有 HTML 由另一个渲染器产出，
    在列表续行、内联空白等处与本脚本有稳定的风格差异——逐字节比对会被这些
    无害差异淹没，反而盖住真正的失同步（例如第 11 章曾整节内容只存在于 HTML）。
    要逐字节口径时加 --strict。
    """
    # 一并去掉星号：本仓库有若干粗体因 CommonMark 的 flanking 规则不生效，
    # 生成侧保留字面 `**`、既有 HTML 却渲染成了标签，属已知的风格差异而非失同步
    # （用 --lint 单独体检这类写法）。
    return re.sub(r"[\s*]+", "", TAG_RE.sub("", html_fragment))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true", help="比对章节内容，不一致则 exit 1")
    g.add_argument("--write", action="store_true", help="用 markdown 重新生成章节 HTML")
    g.add_argument("--diff", action="store_true", help="打印差异，不写文件")
    g.add_argument("--lint", action="store_true",
                   help="体检 markdown：找出标准 markdown 下不会渲染的粗体")
    ap.add_argument("--strict", action="store_true",
                    help="--check/--diff 改用逐字节比对（默认只比内容文本）")
    ap.add_argument("chapters", nargs="*", metavar="chN", help="留空表示全部章节")
    args = ap.parse_args()

    files = chapter_files()
    targets = args.chapters or list(files)
    if unknown := [c for c in targets if c not in files]:
        print(f"❌ 未知章节：{unknown}；可选 {list(files)}")
        return 2

    if args.lint:
        total = 0
        for cid in targets:
            bad = lint_bold(files[cid].read_text(encoding="utf-8"))
            if bad:
                print(f"\n{files[cid].name}（{len(bad)} 处）")
                for lineno, span in bad:
                    print(f"  :{lineno}  {span}")
            total += len(bad)
        if total:
            print(f"\n⚠️  合计 {total} 处粗体在标准 markdown 下不会渲染"
                  "（收尾 ** 前是标点、后是汉字）。")
            print("   修法：把标点移出加粗范围，如 **残差流（x）**上 → **残差流**（x）上。")
            return 1
        print("✅ 未发现失效粗体")
        return 0

    html = INDEX.read_text(encoding="utf-8")
    stale = []
    for cid in targets:
        if cid in MANUAL_CHAPTERS:
            print(f"  ⏭️  {cid} 跳过：{MANUAL_CHAPTERS[cid]}")
            continue
        gen = generated_body(cid, files[cid], html)
        cur = existing_body(html, cid)
        # --write 一律按逐字节判断（内容相同但排版不同也要重写）；
        # --check/--diff 默认只比内容，加 --strict 才逐字节。
        byte_same = gen.strip() == cur.strip()
        same = byte_same if (args.strict or args.write) else text_of(gen) == text_of(cur)
        if same:
            if args.write:
                print(f"  ✅ {cid} 已是最新")
            continue
        stale.append(cid)
        if args.diff:
            import difflib
            d = list(difflib.unified_diff(cur.split("\n"), gen.split("\n"),
                                          f"{cid} (index.html)", f"{cid} (由 markdown 生成)",
                                          n=1, lineterm=""))
            print("\n".join(d[:150]))
        elif args.write:
            write_chapter(cid, files[cid])
            print(f"  ✍️  {cid} 已重新生成")
            html = INDEX.read_text(encoding="utf-8")

    if args.check:
        scope = "逐字节" if args.strict else "内容"
        if stale:
            print(f"❌ {scope}比对不通过：{' '.join(stale)}")
            print("   修复：python3 build_chapter_html.py --write " + " ".join(stale))
            return 1
        print(f"✅ {len(targets)} 章的 HTML 与 markdown 一致（{scope}口径）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
