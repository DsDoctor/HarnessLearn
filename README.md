# HarnessLearn — 学习 Agent 手搓 Harness

> 从一次模型调用开始，一步步手搓出一个小 harness。
> 进度跟着理解走，不求快 —— 每一步都建立在"上一步真的看懂了"之上。

仓库：https://github.com/DsDoctor/HarnessLearn

## 项目结构约定

**每一次演进 = 一个目录**：描述写在各自的 `README.md`（主要阅读材料），
代码里只保留最关键的注释。**看懂的东西沉淀成可复用代码，收进 `llmkit/`。**

```
llmkit/                 共用工具包：多提供方注册表、读 .env、建 client（切提供方只改 .env 一行）
steps/
├── step1_bare_call/      ✅ 裸调用：一次完整的模型调用（已过关）
├── step2_streaming/      ✅ 流式调用：chunk、增量、思考流/正文流（已过关）
└── step3_agent_loop/     🎯 最简 agent loop：工具 + 循环 = agent（当前步骤）
```

运行方式（都在项目根目录下）：

```bash
.venv/bin/python steps/step1_bare_call/bare_call.py
.venv/bin/python steps/step2_streaming/stream_call.py
.venv/bin/python steps/step3_agent_loop/agent_loop.py                # 默认演示问题
.venv/bin/python steps/step3_agent_loop/agent_loop.py "你的问题"      # 自定义问题
```

## 学习路线

| 步 | 目录 | 状态 | 学什么 |
|---|---|---|---|
| 1 | `step1_bare_call` | ✅ 已过关 | 一次调用的全部：messages、参数、返回结构、token |
| 2 | `step2_streaming` | ✅ 已过关 | 流式：chunk、增量、思考流/正文流、打字机效果 |
| 3 | `step3_agent_loop` | 🎯 当前 | 工具 + 循环 = agent：消息喂回、记忆长胖、两个出口 |
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

- **提供方与密钥**：llmkit 内置一张提供方注册表（`llmkit/config.py` 的 `PROVIDERS`），
  密钥只放在项目根目录 `.env`（已进 `.gitignore`，不会上传），模板见 `.env.example`。
  当前用哪个提供方，由 `.env` 的 `LLM_PROVIDER` 一行决定：
  - `zenmux` —— `z-ai/glm-5.3-flashx`，直连不通，走本机代理
  - `nvidia` —— `deepseek-ai/deepseek-v4.1-flash`，国内直连

  **切换 = 改一行；新增提供方 = 注册表加一条 + `.env` 放密钥；换模型 = `<提供方>_MODEL` 覆盖。**
  这套升级是被逼出来的：代理一挂，单提供方项目就瘫了（实测教训）。
- **代理**：只有 zenmux 需要本机代理（127.0.0.1:7897），而且代理只挂在 zenmux 自己的
  client 上，不污染全局环境变量；git 推送也走这个代理。
- **坑**：`api_key="$XXX"` 在 Python 里是字面字符串，不会展开环境变量
  （那是 Shell 语法），所以代码统一从 `os.environ` 读取。
