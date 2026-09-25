"""
agent_loop.py — 第 3 步：最简 Agent Loop（⚠️ 学完 step2 流式之后再来看）

一个 agent 的本质：
    循环 { 把全部历史发给模型 → 模型要么要调工具（执行、结果塞回历史、再来）
          → 要么给出最终回答（结束） }

详细解释见本目录 README.md。

运行（在项目根目录下）：
    .venv/bin/python steps/step3_agent_loop/agent_loop.py                # 默认演示问题
    .venv/bin/python steps/step3_agent_loop/agent_loop.py "帮我看看这个目录里有什么"
"""

import json
import subprocess
import sys
from pathlib import Path

# 把项目根目录加进 import 搜索路径，才能找到共用的 llmkit 包
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from llmkit import get_client, get_model  # noqa: E402  必须放在上面 path 调整之后

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


# ---------- Agent Loop：harness 的心脏 ----------
def memory_shape(messages) -> str:
    """把 messages 压缩成一行"角色序列"，让 agent 的记忆形状肉眼可见。

    注意列表里混着两种东西：我们自己 append 的 dict，和模型返回的 message 对象。
    （真实 harness 里通常会统一成 dict —— 这里保留原样，正好看清这个事实）
    getattr 对两种都成立：dict 没有该属性时返回 None，不会抛错。
    """
    parts = []
    for m in messages:
        role = m["role"] if isinstance(m, dict) else m.role
        if getattr(m, "tool_calls", None):  # 带 tool_calls 的 assistant = "我想调工具"
            role += "(要🔧)"
        parts.append(role)
    return " → ".join(parts)


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
        print(f"[turn {turn}] 📜 记忆形状: {memory_shape(messages)}")

        # 第 1 步：把全部历史发给模型（和 step1 相同，只多传 tools=）
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SPEC,
            temperature=0.5,
            top_p=1,
            max_tokens=2048,
            stream=False,
        )
        msg = completion.choices[0].message

        # 每轮 token 在增长 —— 这就是以后要做"上下文管理"的原因
        if completion.usage:
            print(f"[turn {turn}] (本轮上下文共 {completion.usage.total_tokens} tokens)")

        # 第 2 步：模型要调工具 → 执行，把结果喂回 messages
        if msg.tool_calls:
            messages.append(msg)
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"[turn {turn}] 🔧 模型调用 {name}({args})")

                result = TOOL_FUNCS[name](**args)  # ← 真正的执行发生在这里
                print(f"[turn {turn}] 📄 工具返回: {result[:300]}")

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
            continue  # 带着工具结果进入下一轮

        # 第 3 步：模型不再要工具 → 最终回答
        print(f"[turn {turn}] 💬 模型给出最终回答")
        return msg.content or ""

    # 保险丝：防止模型无限调工具烧光 token
    return "(达到 max_turns 上限，agent 没能给出最终回答)"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or (
        "看看当前目录里都有哪些文件，然后用 python 帮我验证一下 "
        "9.11 和 9.8 哪个数字更大。"
    )
    print(f"🙋 用户: {question}\n")
    answer = agent_loop(question)
    print(f"\n🤖 Agent: {answer}")
