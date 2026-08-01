#!/usr/bin/env python3
"""serve.py — 手册学习网站的静态服务器（纯标准库，零依赖）

相比 `python3 -m http.server` 的改进：
  · gzip 压缩：index.html 2.3MB → 约几百 KB，公网/中转访问明显提速
    （按文件 mtime 做内存缓存，文件更新后自动重新压缩）
  · 多线程：多设备同时访问不互相阻塞
  · .md/.txt 以 UTF-8 文本返回，浏览器可直接阅读章节源文件
  · html 带 Cache-Control: no-cache，内容更新后刷新即见

用法：
  python3 serve.py            # 0.0.0.0:8000
  PORT=9000 python3 serve.py  # 换端口
"""
import gzip
import os
import sys
import threading
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", "8000"))
GZIP_EXTS = {".html", ".htm", ".md", ".txt", ".css", ".js", ".json", ".svg", ".xml"}
GZIP_MIN_BYTES = 1024

_gz_cache = {}          # path -> (mtime, gzipped_bytes)
_gz_lock = threading.Lock()


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".md": "text/markdown; charset=utf-8",
        ".txt": "text/plain; charset=utf-8",
    }

    def _is_blocked(self):
        """隐藏文件/目录（.env、.git 等）与越界路径一律 404。

        判断必须基于 translate_path() 解码并规范化后的真实路径：直接看
        self.path 会被 URL 编码绕过（%2Eenv 解码后就是 .env）。realpath
        同时挡住经符号链接逃出 ROOT 的情况。
        """
        real = os.path.realpath(self.translate_path(self.path))
        try:
            rel = os.path.relpath(real, os.path.realpath(ROOT))
        except ValueError:  # 跨盘符等无法比较的情况一律拒绝
            return True
        if rel == ".." or rel.startswith(".." + os.sep):
            return True
        return any(seg.startswith(".") for seg in rel.split(os.sep) if seg not in ("", "."))

    def do_HEAD(self):
        if self._is_blocked():
            self.send_error(404, "File not found")
            return
        super().do_HEAD()

    def do_GET(self):
        if self._is_blocked():
            self.send_error(404, "File not found")
            return
        path = self.translate_path(self.path)
        if os.path.isdir(path) and self.path.endswith("/"):
            index = os.path.join(path, "index.html")
            if os.path.isfile(index):
                path = index
        ext = os.path.splitext(path)[1].lower()
        if (
            ext in GZIP_EXTS
            and "gzip" in self.headers.get("Accept-Encoding", "")
            and os.path.isfile(path)
            and os.path.getsize(path) >= GZIP_MIN_BYTES
        ):
            self._serve_gzipped(path, ext)
        else:
            super().do_GET()

    def _serve_gzipped(self, path, ext):
        mtime = os.path.getmtime(path)
        with _gz_lock:
            cached = _gz_cache.get(path)
        if cached is None or cached[0] != mtime:
            with open(path, "rb") as f:
                data = gzip.compress(f.read(), compresslevel=6)
            with _gz_lock:
                _gz_cache[path] = (mtime, data)
        else:
            data = cached[1]
        self.send_response(200)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Encoding", "gzip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Vary", "Accept-Encoding")
        if ext in (".html", ".htm"):
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    os.chdir(ROOT)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Serving {ROOT} on 0.0.0.0:{PORT} (gzip + threading)")
    server.serve_forever()
