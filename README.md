# HarnessLearn — 学习 Agent 手搓 Harness

> 从一次模型调用开始，一步步手搓出一个小 harness。
> 进度跟着理解走，不求快 —— 每一步都建立在"上一步真的看懂了"之上。

仓库：https://github.com/DsDoctor/HarnessLearn

## 项目结构约定

**每一次演进 = 一个目录**：描述写在各自的 `README.md`（主要阅读材料），
代码里只保留最关键的注释。**看懂的东西沉淀成可复用代码，收进 `llmkit/`。**

```
llmkit/                 共用工具包：读 .env、建 client、取模型名（换节点只改 .env）
steps/
├── step1_bare_call/      ✅ 裸调用：一次完整的模型调用（已过关）
├── step2_streaming/      🎯 流式调用：分步看到模型怎么"流"出来（当前步骤）
└── step3_agent_loop/     ⏸ 最简 agent loop（学完 step2 再打开）
```

运行方式（都在项目根目录下）：

```bash
.venv/bin/python steps/step1_bare_call/bare_call.py
.venv/bin/python steps/step2_streaming/stream_call.py
```

## 学习路线

| 步 | 目录 | 状态 | 学什么 |
|---|---|---|---|
| 1 | `step1_bare_call` | ✅ 已过关 | 一次调用的全部：messages、参数、返回结构、token |
| 2 | `step2_streaming` | 🎯 当前 | 流式：chunk、增量、思考流/正文流、打字机效果 |
| 3 | `step3_agent_loop` | ⏸ 下一站 | 工具 + 循环 = agent |
| 4+ | 以后再建 | 预告 | 见下面的路线图 |

## 之后的路线图（只做预告，不展开）

| 步 | 加什么 | 解决什么问题 |
|---|---|---|
| 4 | 工具注册表 + read / write / edit 文件工具 | 只有一个 bash 太糙；细粒度工具更可控、好审计 |
| 5 | 上下文管理：截断 / 压缩 / 摘要 | messages 越滚越长，token 爆炸 |
| 6 | 沙箱与审批：命令白名单、危险操作先问用户 | 模型说 `rm -rf` 你敢直接执行吗？ |
| 7 | 子 agent / 任务委派 | 一个 loop 干不了大事 |
| 8 | 持久化目标、断点续跑 | 跨会话续干活的 "goal" 系统 |

你现在用的 DeepSeek Harness，本质就是第 8 步的形态 ——
但它的心脏，仍然是 step3 里那个循环。

## 通用说明

- **节点与密钥**：全部配置在项目根目录 `.env`（已进 `.gitignore`，不会上传），模板见 `.env.example`。
  当前节点 zenmux（`https://zenmux.ai/api/v1`，模型 `z-ai/glm-5.3-flashx`）。
  **以后换节点 / 换模型 = 只改 `.env`，所有代码一行不动** —— 这就是 llmkit 存在的意义。
- **代理**：zenmux 直连不通，`.env` 里的 `LLM_PROXY` 指向本机代理（127.0.0.1:7897）；
  git 推送也已配置走同一个代理。
- **坑**：`api_key="$XXX"` 在 Python 里是字面字符串，不会展开环境变量
  （那是 Shell 语法），所以代码统一从 `os.environ` 读取。
