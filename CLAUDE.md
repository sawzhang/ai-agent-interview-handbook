# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目性质

中文 AI Agent 面试学习手册——内容型仓库，无构建系统、无依赖、无测试框架。全部内容为简体中文，提交信息也用中文。

## 常用命令

```bash
# 运行单个实验（labs 是唯一的可执行代码，纯 Python 标准库，零依赖）
cd labs && python3 lab01_react_agent.py

# 全部实验一次跑完（这就是本仓库的"测试套件"：每个 lab 内置 assert 自检，
# 成功打印 ✅ 自检通过；任何 assert 失败即为回归）
cd labs && for f in lab*.py; do python3 "$f"; done

# 提供学习网站（零依赖：gzip + 多线程 + 隐藏文件/目录列表屏蔽）
python3 serve.py            # 默认 0.0.0.0:8000
PORT=8080 python3 serve.py  # 换端口

# 接入真实 LLM（阿里云百炼 Anthropic 兼容网关；无 Key 时 lab09 自动降级为 Mock）
export DASHSCOPE_API_KEY='sk-sp-...'
python3 labs/llm_client.py               # 连通性自检
python3 labs/lab09_real_llm_react.py     # 真实 tool-use ReAct
```

## 核心架构：同一份章节内容存在于四处，改内容必须同步

这是本仓库最重要的约束。修改任何章节内容时，以下四处必须保持一致：

1. **`chapters/NN-章名.md`** — 按章拆分的 Markdown（00-开篇导读 + 01~14 章），精读用的规范来源。
2. **`AI-Agent面试学习手册.md`** — 单文件全书，是 chapters/ 的拼接（章标题格式 `# 第 N 章 · 标题`），供全文检索/导入笔记软件。
3. **`index.html` 的章节 HTML** — 手工维护的单文件学习网站（约 2.3MB，全部 CSS/JS 内联、无外部依赖）。每章是 `<section id="chN" class="chapter">`，含 `minitoc` 本章导航，小节锚点为 `#chN-sM`。
4. **`index.html` 内联脚本里的搜索索引** — 最后一个 `<script>` 块开头的 `const SECTIONS=[{"id":"ch1","title":...,"text":...}]`，是每章内容的**小写纯文本副本**（预构建索引）。只改章节 HTML 而不更新对应 SECTIONS 条目，站内搜索会返回过期结果。**不要手改**，改完章节 HTML 后跑：

```bash
python3 build_search_index.py          # 从章节 HTML 重建 SECTIONS
python3 build_search_index.py --check   # 索引过期则 exit 1（可做提交前检查）
```

派生内容视改动范围联动更新：`考前速记表.md`（浓缩考点）、`模拟面试追问链.md`（10 条追问链）、`flashcards/`（anki_cards.txt 为制表符分隔的 Anki Basic 卡片，格式 `[章节] 问题<TAB>答案`，答案内含 HTML 标签与实体）。

### 操作提示

- `index.html` 超过 2MB，**不要整读**；用 grep 定位 `id="chN"` 或小节锚点后做局部编辑。
- 每章固定 6 模块结构（第 11 章为 7 节）：知识图谱 → 核心概念精讲 → 面试高频考点（⭐分级）→ 经典面试题与参考答案 → 易错点·反直觉点 → 推荐资源。新增章节/小节须沿用此结构。
- 站点特性依赖现有 DOM 约定：侧边栏导航、搜索、暗黑主题（`[data-theme="dark"]` + localStorage）、打印分页（`.chapter{page-break-before:always}`）。改 HTML 结构时保持 class/id 约定不变。

## labs/ 代码约定

- 纯标准库、零第三方依赖，这是硬性约定；新 lab 同样遵守。
- 每个 lab 的 Mock LLM 都实现 `chat()`/`__call__` 接口，与 `llm_client.py` 的 `QwenLLM` 同构，可互换（lab09 演示了真实/Mock 同构切换的标准写法）。
- 每个 lab 文件：顶部 docstring（目的/核心概念/思考题）+ 末尾 assert 自检 + 打印 `✅ 自检通过`。

## 安全

- API Key 一律从环境变量读取（优先级 `DASHSCOPE_API_KEY` → `BAILIAN_API_KEY` → `ANTHROPIC_AUTH_TOKEN` → `TOKENPLAN_API_KEY`），绝不硬编码、绝不提交；`.gitignore` 已覆盖 `.env*`/`*.key`/`*.pem`/`credentials*.json` 等一整类凭据文件。
- `serve.py` 的 `_is_blocked()` **必须基于 `translate_path()` 解码后的真实路径判断**——直接检查 `self.path` 会被 URL 编码绕过（`%2Eenv` 解码后就是 `.env`），曾据此泄露过 `labs/.env`。改动这个函数后请回归：`/labs/%2Eenv`、`/%2Egit/config`、`/labs/`、`/../../etc/passwd` 均应 404。
- 仓库中的绝对路径会暴露本机目录结构：labs 与文档里的示例命令一律写成 `cd labs && python3 xxx.py` 的相对形式。

## 许可

见 `LICENSE`：文字内容 CC BY-NC-SA 4.0，代码（`labs/*.py`、`serve.py`、`build_search_index.py`）MIT。新增内容默认沿用对应许可。
