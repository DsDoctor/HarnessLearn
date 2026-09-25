# 第 3 步：最简 Agent Loop —— 工具 + 循环 = Agent

**状态：🎯 当前步骤**

```bash
# 运行（在项目根目录下）
.venv/bin/python steps/step3_agent_loop/agent_loop.py                # 默认演示问题
.venv/bin/python steps/step3_agent_loop/agent_loop.py "你的问题"      # 自定义问题
```

## 兑现上一版埋下的两条核心认知

上一版 README 说"step2 过关了再打开"。现在兑现：

1. **`messages` 列表就是 agent 的全部记忆与状态。**
   harness 里所有花哨概念（上下文管理、压缩、记忆），本质都是在管理这张列表。
   本步新增的「记忆形状」打印（每轮开头那行 📜）就是让这件事肉眼可见。
2. **模型从不执行任何东西，它只输出"我想执行 X"。**
   真正的执行永远发生在你自己的 Python 进程里 —— 模型的"手"其实是你的手。
   所以"权限 / 沙箱 / 审批"这些 harness 概念才会存在（第 6 步的主题）。

## 从 step1 到 step3，只多了三样东西

| # | 加什么 | 在代码里是 |
|---|---|---|
| 1 | 一个工具 + 它的说明书 | `run_bash()` + `TOOLS_SPEC`（JSON Schema，给模型看的） |
| 2 | `create()` 多传一个参数 | `tools=TOOLS_SPEC` |
| 3 | 一个循环 | 要工具 → 执行 → 结果塞回 `messages` → 再问，直到最终回答 |

其余全是 step1 就见过的东西。**agent ≠ 更强的模型，agent = 模型 + 一圈胶水。**

## 协议：模型怎么"说要调工具"

三段式，每一段长什么样：

**① 请求侧（你 → 模型）**，`tools=` 是"工具说明书"：
```python
{"type": "function",
 "function": {"name": "run_bash",
              "description": "在用户的 macOS 上执行一条 shell 命令并返回输出…",
              "parameters": {"type": "object",           # ← 这是一段 JSON Schema
                             "properties": {"command": {"type": "string", …}},
                             "required": ["command"]}}}
```

**② 响应侧（模型 → 你）**，`choices[0].message` 多出一个字段：
```python
msg.tool_calls[0].id                  # "call_abc123" —— 回填结果时对号入座
msg.tool_calls[0].function.name       # "run_bash"
msg.tool_calls[0].function.arguments  # '{"command": "ls"}'  ⚠️ JSON 字符串，不是 dict！
```

**③ 回填侧（你 → 模型）**，执行结果作为一种新角色进 `messages`：
```python
{"role": "tool", "tool_call_id": "call_abc123", "content": "命令的输出"}
```

两个容易忽视的细节：
- **要工具的 assistant 消息本身也要先 append**（先记"我要求过什么"，再记"结果是什么"），
  顺序不能反 —— 下一轮模型要能看到自己上一轮的请求，才知道结果对应谁。
- **`content` 只能是字符串**。命令输出一万行也得是字符串 ——
  截断、转存文件，是真实 harness 的日常操作。

## 循环的两个出口 + 一个保险丝

```text
while True:
    回复 = 模型(全部历史 messages)
    if 回复.要求调用工具:
        结果 = 执行工具(回复.工具调用)
        把"请求 + 结果"都追加进 messages      # 喂回
    else:
        return 回复.内容        # 出口①：模型不再要工具 = 它认为做完了
    if 轮数超过 max_turns:
        return "(熔断)"         # 出口②：保险丝
```

`max_turns` 是本项目遇到的第一个**安全机制**：不信任模型的自我节制，用硬上限兜底。
真实 harness 的权限 / 审批系统方向完全一致，只是精细得多。

## 一次真实运行的解剖（2026-09-26 实跑，nvidia 直连）

> 这次实跑正好赶上本机代理故障（zenmux 走不了），靠 llmkit v2 切到 nvidia 直连完成
> —— 多提供方互为备份，第一次实战就派上用场。

```
🙋 用户: 看看当前目录里都有哪些文件，然后用 python 帮我验证一下 9.11 和 9.8 哪个数字更大。

[turn 1] 📜 记忆形状: system → user
[turn 1] (本轮上下文共 551 tokens)
[turn 1] 🔧 模型调用 run_bash({'command': 'ls -la'})
[turn 1] 📄 工具返回: total 40
drwxr-xr-x@ 13 ds  staff   416 Sep 26 01:18 .
…（目录列表；打印截断到 300 字，但完整内容进了 messages）
[turn 1] 🔧 模型调用 run_bash({'command': 'python3 -c "print(\'9.11 > 9.8 :\', 9.11 > 9.8); …"'})
[turn 1] 📄 工具返回: 9.11 > 9.8 : False
9.11 < 9.8 : True
max = 9.8

[turn 2] 📜 记忆形状: system → user → assistant(要🔧) → tool → tool
[turn 2] (本轮上下文共 1228 tokens)
[turn 2] 💬 模型给出最终回答

🤖 Agent: ## 当前目录内容 …（列出了目录）
## 9.11 vs 9.8 的比较结果 …（引用 python 输出）**结论：9.8 更大。**
（还主动提醒：版本号的 9.11 > 9.8 是另一套比较规则，问要不要写个版本号比较工具）
```

三个值得盯住的细节：

1. **turn 1 里模型一口气要了两个工具**（`ls` 和 `python3`）：
   一次 assistant 回复可以携带多个 tool_calls，harness 逐个执行、逐个回填 ——
   所以 turn 2 的记忆形状是 `assistant(要🔧) → tool → tool`（一条请求，两个结果）。
2. **上下文只进不出**：551 → 1228 tokens，一轮就翻倍。轮数一多，这就是滚雪球的账单
   —— 第 5 步（上下文管理）的问题意识，此刻已经能看到。
3. **模型全程只看了目录，但它完全可以 `cat .env` 把密钥读走** —— 没有任何东西拦它。
   这个"完全信任"就是第 6 步（沙箱与审批）要解决的问题，它此刻已经真实存在。

## 记忆形状：亲眼看 messages 长胖

每轮开头的打印（示意，以实际运行输出为准）：
```
[turn 1] 📜 记忆形状: system → user
[turn 2] 📜 记忆形状: system → user → assistant(要🔧) → tool
[turn 3] 📜 记忆形状: system → user → assistant(要🔧) → tool → assistant(要🔧) → tool
[turn 4] 📜 记忆形状: … → assistant          ← 不再要工具，循环在本轮结束
```

配合每轮的 token 计数看：**上下文只进不出，每一轮都在变贵** ——
这就是第 5 步（上下文管理）要解决的问题，此刻已经能看到它的影子。

## 最容易踩的坑（前三个真实 harness 必须防，这里故意不防）

1. **`arguments` 是 JSON 字符串**：`json.loads()` 之前它只是一段文本。
2. **模型可能"幻觉"出不存在的工具**：叫一个注册表里没有的名字 → `KeyError` 直接崩。
   真实 harness 会把"没有这个工具"作为工具结果喂回去，让模型自己纠错。
3. **模型可能给坏 JSON**：`json.loads()` 抛异常，循环死在半路。
4. **`messages` 里混着两种东西**：自己 append 的 dict 和模型返回的 message 对象
   （`memory_shape()` 里那个 `isinstance` 分支就是在伺候这个）。真实 harness 通常统一转成 dict。

> 教学代码故意不防这些 —— 防护代码会淹没主干。
> 动手实验 5 会让你**亲手触发一次**坑 2，眼见为实。

## 流式去哪了？

step3 故意退回 `stream=False`：这一步要看清"循环"这个主干，别让流的细节搅局。
真实 harness（比如你现在用的 DSH）是两者的合体：
**用 step2 的方式流式接收，跑 step3 的循环** —— 工具调用同样以增量 chunk 流出。
合体方法见动手实验 6。

## 理解检查

1. 模型"调用工具"时，执行代码跑在哪一侧？API 服务器还是你的 Python 进程？
2. 工具结果通过什么角色、哪两个关键字段回到模型眼前？
3. `tool_call.function.arguments` 是什么类型？不 `json.loads` 直接当 dict 用会怎样？
4. 要工具的 assistant 消息和工具结果的 tool 消息，哪条必须先进 `messages`？为什么？
5. 循环的两个出口分别是什么？`max_turns` 防的是什么风险？
6. 工具说明书里的 `description` 写得好坏，影响模型的什么？
   （想想第 1 步里 system prompt 的作用 —— 这是同一个道理，只是作用在单件工具上）

## 动手实验

1. **看记忆长胖**：跑默认演示问题，数每轮「记忆形状」多了几个角色，token 计数涨了多少
2. **问一个不需要工具的问题**（如"你好"）：看它 turn 1 就给最终回答，记忆形状不再变长
3. **加第二个工具**（如 `read_file(path)`）：只需在 `TOOL_FUNCS` 和 `TOOLS_SPEC` 各加一条
   —— 这就是"工具注册表"的雏形，第 4 步的主题
4. **把 `max_turns` 改成 1**：亲眼看保险丝熔断，agent 被掐死在半路
5. **制造一次事故**：把 `TOOLS_SPEC` 里的名字改成 `bash_run`（`TOOL_FUNCS` 不动），
   让模型去调 —— 亲眼看 `KeyError` 崩溃，体会真实 harness 必须防什么
6. **（进阶）合体 step2**：把 `stream=True` 接进来。提示：`tool_calls` 也在 delta 里，
   要按 `index` 拼装增量 —— 比拼文字难一档，但真实 harness 天天在干
