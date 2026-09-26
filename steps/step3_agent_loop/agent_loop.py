"""
agent_loop.py — 第 3 步：最简 Agent Loop

一个 agent 的本质：
    循环 { 把全部历史发给模型 → 模型要么要调工具（执行、结果塞回历史、再来）
          → 要么给出最终回答（结束） }

直接运行（PyCharm 点运行也一样）＝ 流式直播：
    每个 chunk 的处理就是一次"解析"：原始结构（delta 对象）→ 取字段 → 按类型拼装。
      - 🆕 每种结构第一次出现时，先打一行完整 repr 看全貌（字段名、嵌套关系一目了然）
      - 之后每个 chunk 一行浓缩行 —— 字段路径就是解析时要走的路
    且每轮把 发出的完整 messages / 拼装出的 assistant 消息 / 回填的 tool 消息
    按真实 JSON 全文打印（这就是线上流动的格式）

想对比 step1 的"一次性接收"：把下面的 USE_STREAM 改成 False（无需运行参数）。

详细解释见本目录 README.md。

运行（在项目根目录下）：
    .venv/bin/python steps/step3_agent_loop/agent_loop.py                # 默认演示问题
    .venv/bin/python steps/step3_agent_loop/agent_loop.py "你的问题"      # 自定义问题
"""

import json
import subprocess
import sys
from pathlib import Path

# 把项目根目录加进 import 搜索路径，才能找到共用的 llmkit 包
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from llmkit import get_client, get_model  # noqa: E402  必须放在上面 path 调整之后

# 接收方式：True=流式直播（默认，点运行即所见）；False=一次性接收（对比 step1 用）
USE_STREAM = True

client = get_client()
MODEL = get_model()


# ---------- 工具：agent 的"手" ----------
def run_bash(command: str) -> str:
    """执行一条 shell 命令并返回输出。最经典的最小 agent 工具。"""
    try:
        proc = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=15
        )
        output = (proc.stdout + proc.stderr).strip()
        return output or "(命令执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"(命令超时：{command})"


# 工具注册表：名字 → Python 函数。加工具 = 往这两个结构里各加一条。
TOOL_FUNCS = {"run_bash": run_bash}

# 给模型看的"工具说明书"（JSON Schema）。description 越清楚，模型用得越准。
TOOLS_SPEC = [
    {
        "type": "function",
        "function": {
            "name": "run_bash",
            "description": (
                "在用户的 macOS 上执行一条 shell 命令并返回输出。"
                "可用于查看目录、读写文件、运行脚本、做计算等。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "要执行的命令，例如 ls -la",
                    },
                },
                "required": ["command"],
            },
        },
    }
]


# ---------- 打印辅助 ----------
def memory_shape(messages) -> str:
    """把 messages 压缩成一行"角色序列"，让 agent 的记忆形状肉眼可见。

    模型返回统一转成 dict 之后，这里不需要 isinstance 分支 ——
    真实 harness 里消息一律是 dict（能 json.dumps、能落盘、能直接当请求体）。
    """
    parts = []
    for m in messages:
        role = m["role"]
        if m.get("tool_calls"):  # 带 tool_calls 的 assistant = "我想调工具"
            role += "(要🔧)"
        parts.append(role)
    return " → ".join(parts)


def dump(messages, title: str) -> None:
    """把消息按真实 JSON 格式全文打印 —— 这就是线上流动的样子。"""
    print(title)
    print(json.dumps(messages, ensure_ascii=False, indent=2))


# ---------- 两种"问模型"：流式（默认） vs 一次性（对比用） ----------
def ask_model_stream(messages):
    """stream=True：逐 chunk 接收、打印、拼装成一条 assistant dict。

    三种增量要分开拼（这是流式 + 工具的真正难点）：
      - 思考 / 正文：纯文本，直接 +=
      - 工具调用：按 delta 里的 index 对号入座；id、name 一般只在第一片出现，
        arguments 是一段段字符串碎片，要自己接起来
    """
    stream = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS_SPEC,
        temperature=0.5,
        top_p=1,
        max_tokens=2048,
        stream=True,
        stream_options={"include_usage": True},
    )

    content, reasoning = "", ""
    tool_calls = {}  # index → {"id", "name", "arguments"}
    usage = None
    n = 0
    seen = set()

    def first_look(kind, obj):
        """某种原始结构第一次出现时完整打一遍 —— 看清模型到底给了什么。"""
        if kind not in seen:
            seen.add(kind)
            print(f"  [chunk {n}] 🆕 原始结构首见[{kind}] {obj!r}")

    for chunk in stream:
        n += 1
        if not chunk.choices:  # 坑：zenmux 最后发一个只带 usage 的空 chunk
            first_look("空chunk·只带usage", chunk)
            usage = chunk.usage or usage
            continue
        choice = chunk.choices[0]
        delta = choice.delta

        # 坑：字段可能整个缺失（缺失≠None，是直接 AttributeError）—— 一律 getattr 防御
        if getattr(delta, "role", None):
            first_look("首个chunk·delta全貌", delta)
            print(f"  [chunk {n}] role = {delta.role!r}")
        r_piece = getattr(delta, "reasoning_content", None) or getattr(delta, "reasoning", None)
        if r_piece:
            print(f"  [chunk {n}] reasoning += {r_piece!r}")
            reasoning += r_piece
        c_piece = getattr(delta, "content", None)
        if c_piece:
            print(f"  [chunk {n}] content += {c_piece!r}")
            content += c_piece
        for tc in getattr(delta, "tool_calls", None) or []:
            first_look("工具调用增量·嵌套最深", delta)
            slot = tool_calls.setdefault(tc.index, {"id": "", "name": "", "arguments": ""})
            if tc.id:
                slot["id"] = tc.id
                print(f"  [chunk {n}] tool_calls[{tc.index}].id = {tc.id!r}")
            if tc.function:
                if tc.function.name:
                    slot["name"] += tc.function.name
                    print(f"  [chunk {n}] tool_calls[{tc.index}].function.name = {tc.function.name!r}")
                if tc.function.arguments:
                    slot["arguments"] += tc.function.arguments
                    print(f"  [chunk {n}] tool_calls[{tc.index}].function.arguments += {tc.function.arguments!r}")
        if choice.finish_reason:
            first_look("finish_reason·挂在choice上", choice)
            print(f"  [chunk {n}] finish_reason = {choice.finish_reason!r}")
        if chunk.usage:
            usage = chunk.usage

    if usage:
        print(f"  (本轮：{n} 个 chunk，思考 {len(reasoning)} 字，上下文共 {usage.total_tokens} tokens)")
    else:
        print(f"  (本轮共 {n} 个 chunk)")

    # 拼装成品：一条普通的 assistant dict。
    # 思考过程不进历史 —— 它不属于消息协议，各家接口也未必收；真实 harness 同样只留 content 和 tool_calls
    msg = {"role": "assistant", "content": content or None}
    if tool_calls:
        msg["tool_calls"] = [
            {
                "id": s["id"],
                "type": "function",
                "function": {"name": s["name"], "arguments": s["arguments"]},
            }
            for _, s in sorted(tool_calls.items())
        ]
    return msg


def ask_model_once(messages):
    """stream=False：一次性接收（对比用，把 USE_STREAM 改成 False 走这条路）。

    同样的信息，另一种到货方式：不是几百个小 chunk，而是一个完整对象 ——
    原始结构和解析成 dict 的过程同样打印出来，和流式版对照看。
    """
    completion = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS_SPEC,
        temperature=0.5,
        top_p=1,
        max_tokens=2048,
        stream=False,
    )
    if completion.usage:
        print(f"  (本轮上下文共 {completion.usage.total_tokens} tokens)")
    m = completion.choices[0].message
    print(f"  🆕 原始结构[整个 message 对象] {m!r}")
    # 统一转成普通 dict 再返回（真实 harness 的做法）
    msg = {"role": "assistant", "content": m.content}
    if m.tool_calls:
        msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in m.tool_calls
        ]
    return msg


# ---------- Agent Loop：harness 的心脏 ----------
def agent_loop(user_input: str, max_turns: int = 8) -> str:
    # messages 是 agent 的全部记忆：每轮模型回复、每次工具结果都追加进来
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个运行在用户 macOS 电脑上的助手。"
                "需要时可以使用 run_bash 工具来查看目录、读写文件、运行脚本。"
                "始终用与用户相同的语言回答。"
            ),
        },
        {"role": "user", "content": user_input},
    ]

    for turn in range(1, max_turns + 1):
        # 第 0 步：先看一眼这次要发给模型的全部记忆 —— 它每一轮都在变长
        print(f"\n[turn {turn}] 📜 记忆形状: {memory_shape(messages)}")

        # 第 1 步：把全部历史发给模型（和 step1 相同，只多传 tools=）
        if USE_STREAM:
            dump(messages, f"[turn {turn}] ⬆️ 发给模型的完整 messages（真实请求体）:")
            msg = ask_model_stream(messages)
            dump([msg], f"[turn {turn}] 🧩 从流里拼装出的 assistant 消息（即将进入记忆）:")
        else:
            msg = ask_model_once(messages)

        # 第 2 步：模型要调工具 → 执行，把结果喂回 messages
        if msg.get("tool_calls"):
            messages.append(msg)
            for tc in msg["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"])
                print(f"[turn {turn}] 🔧 模型调用 {name}({args})")

                result = TOOL_FUNCS[name](**args)  # ← 真正的执行发生在这里
                tool_msg = {"role": "tool", "tool_call_id": tc["id"], "content": result}
                dump([tool_msg], f"[turn {turn}] 📄 回填的 tool 消息（即将进入记忆）:")
                messages.append(tool_msg)
            continue  # 带着工具结果进入下一轮

        # 第 3 步：模型不再要工具 → 最终回答
        print(f"[turn {turn}] 💬 模型给出最终回答")
        return msg.get("content") or ""

    # 保险丝：防止模型无限调工具烧光 token
    return "(达到 max_turns 上限，agent 没能给出最终回答)"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or (
        "看看当前目录里都有哪些文件，然后用 python 帮我验证一下 "
        "9.11 和 9.8 哪个数字更大。"
    )
    print(f"🙋 用户: {question}")
    print(f"（接收方式：{'流式直播' if USE_STREAM else '一次性接收'}）\n")
    answer = agent_loop(question)
    print(f"\n🤖 Agent: {answer}")
