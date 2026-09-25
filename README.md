# HarnessLearn — 学习 Agent 手搓 Harness

> 从一次模型调用开始，一步步手搓出一个小 harness。
> 进度跟着理解走，不求快 —— 每一步都建立在"上一步真的看懂了"之上。

仓库：https://github.com/DsDoctor/HarnessLearn

## 学习路线（现在在哪）

- ✅ **第 0 步：`bare_call.py` —— 看懂一次完整的模型调用（当前重点）**
- ⏸ 第 1 步：`agent_loop.py` —— 最简 agent loop（**看懂第 0 步之后**再打开，不着急）

## 跑起来

```bash
# 1. 依赖（虚拟环境已建好）
.venv/bin/pip install -r requirements.txt

# 2. 配置 key（.env 已配好则跳过）
cp .env.example .env && vim .env        # 填入 NVIDIA_API_KEY=nvda-xxx

# 3. 第 0 步
.venv/bin/python bare_call.py
```

## 第 0 步：看懂一次模型调用（bare_call.py）

文件里每个概念都有 **英文 + 中文** 双语注释，按从上到下阅读：

| 概念 | 一句话理解 |
|---|---|
| `client` | 记住了"发给谁（base_url）+ 用什么身份（api_key）"，后面调用就不用重复写 |
| `messages` | 模型能看到的**全部**输入，就这一张列表，没有别的 |
| `role: system` | 助手的"岗位说明书"，开发者设定 |
| `role: user` | 用户实际问的问题 |
| `temperature` | 随机程度：低→稳定事实，高→发散创意 |
| `max_tokens` | 回复长度硬上限，撞到就截断（finish_reason 变 "length"） |
| `stream` | False=一次拿全；True=边生成边返回（打字机效果） |
| `choices[0].message.content` | 回答正文 |
| `finish_reason` | 模型为什么停笔：`stop`=说完，`length`=被截断 |
| `usage` | token 账单：输入多少、输出多少 |
| `reasoning_content` | 推理模型的"内心思考"，不属于回答本身 |

**理解检查 —— 能自信回答这四个问题，第 0 步就过关了：**

1. 模型一次请求能"看到"的全部东西是什么？
2. 把 `temperature` 从 0.5 调到 1.5，回答会怎么变？
3. `finish_reason` 显示 `"length"` 说明发生了什么？该调哪个参数？
4. `reasoning_content` 和 `content` 的区别是什么？

## 第 0 步的动手实验

1. 把 user 消息换成你自己的问题，跑一遍
2. 把 `max_tokens` 改成 `10`，观察 `finish_reason` 变成 `length`、回答被拦腰截断
3. 把 `temperature` 改成 `0` 跑两次、再改成 `1.5` 跑两次，对比回答的波动
4. 每次运行注意最后的 token 用量 —— 这就是以后"上下文管理"要省的东西

## 第 1 步（预告，先别急）：agent_loop.py

等你对第 0 步的每个字段都眼熟了再打开它。它**只比第 0 步多三样东西**：

1. 一个工具 `run_bash` —— agent 的"手"
2. `create()` 多传一个 `tools=` 参数 —— 告诉模型它有手可用
3. 一个循环 —— 模型要工具 → 执行 → 结果塞回 `messages` → 再问模型，直到给出最终回答

```
用户提问
   │
   ▼
┌─────────────────────────────┐
│  messages ──► 模型          │
│                │            │
│      要调工具？─┴─ 是 ──► 执行工具
│                │            │ │
│                否            │ └─ 结果追加进 messages（回到顶部）
│                ▼            │
│            最终回答          │
└─────────────────────────────┘
```

核心认知先记两条，到时候再看代码会顺很多：

- **`messages` 列表就是 agent 的全部记忆**。所谓上下文管理、压缩、记忆，都是在管这张不断变长的列表。
- **模型从不执行任何东西**，它只输出"我想执行 X"。真正执行的是你自己 Python 进程里的那一行代码 —— 所以"权限 / 沙箱 / 审批"这些 harness 概念才会存在。

## 之后的路线图（只做预告，不展开）

| 步 | 加什么 | 解决什么问题 |
|---|---|---|
| 2 | 工具注册表 + read / write / edit 文件工具 | 只有一个 bash 太糙；细粒度工具更可控、好审计 |
| 3 | 上下文管理：截断 / 压缩 / 摘要 | messages 越滚越长，token 爆炸 |
| 4 | 沙箱与审批：命令白名单、危险操作先问用户 | 模型说 `rm -rf` 你敢直接执行吗？ |
| 5 | 子 agent / 任务委派 | 一个 loop 干不了大事 |
| 6 | 持久化目标、断点续跑 | 跨会话续干活的 "goal" 系统 |

## 两个小坑

- API key 不要写死在代码里：`api_key="$NVIDIA_API_KEY"` 在 Python 里是**字面字符串**，不会展开环境变量 —— 所以本项目统一 `os.environ` 读取 + 可选 `.env`（`.env` 已被 `.gitignore` 排除，不会上传）。
- `max_tokens` 的单位不是"字数"：一个汉字约 1~2 个 token。
