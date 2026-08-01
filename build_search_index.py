#!/usr/bin/env python3
"""build_search_index.py — 从 index.html 的章节 HTML 重建站内搜索索引（纯标准库）

index.html 内嵌的 `const SECTIONS=[...]` 是每章内容的小写纯文本副本，供全文搜索。
手工改完章节 HTML 后运行本脚本即可重建索引，避免"改了正文、搜索还是旧的"：

    python3 build_search_index.py          # 原地重写 index.html 中的 SECTIONS 行
    python3 build_search_index.py --check  # 只检查是否过期（退出码 1=需要重建）
"""
import html
import json
import re
import sys
import unicodedata

INDEX = "index.html"


def section_text(body: str) -> str:
    """章节 HTML → 索引文本：去标签、解实体、小写、压空白。"""
    body = re.sub(r"<(script|style)\b.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    body = html.unescape(body)
    body = unicodedata.normalize("NFC", body)
    return re.sub(r"\s+", " ", body).strip().lower()


def build(doc: str):
    sections = []
    for m in re.finditer(
        r'<section id="(ch\d+)" class="chapter">(.*?)</section>', doc, re.S
    ):
        cid, body = m.group(1), m.group(2)
        if cid == "ch0":  # 前言不入索引，与原索引行为一致
            continue
        tm = re.search(r'<h1 class="ch-title">(.*?)</h1>', body)
        title = html.unescape(re.sub(r"<[^>]+>", "", tm.group(1))).strip() if tm else cid
        sections.append({"id": cid, "title": title, "text": " " + section_text(body)})
    return sections


def main():
    doc = open(INDEX, encoding="utf-8").read()
    sections = build(doc)
    assert len(sections) == 14, f"预期 14 章，实际解析出 {len(sections)} 章"
    new_line = "const SECTIONS=" + json.dumps(sections, ensure_ascii=False) + ";"
    pattern = re.compile(r"const SECTIONS=\[.*?\];", re.S)
    if not pattern.search(doc):
        sys.exit("未找到 const SECTIONS=[...] 行，index.html 结构可能已变化")
    if "--check" in sys.argv:
        current = pattern.search(doc).group(0)
        if current == new_line:
            print("✅ 搜索索引与正文一致")
        else:
            print("⚠️ 搜索索引已过期，运行 python3 build_search_index.py 重建")
            sys.exit(1)
        return
    open(INDEX, "w", encoding="utf-8").write(pattern.sub(lambda _: new_line, doc, count=1))
    total = sum(len(s["text"]) for s in sections)
    print(f"✅ 已重建 {len(sections)} 章搜索索引，共 {total} 字符")


if __name__ == "__main__":
    main()
