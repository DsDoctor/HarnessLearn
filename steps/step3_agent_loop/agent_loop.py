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
import os
import subprocess
import sys
from pathlib import Path

from openai import OpenAI

# ---------- 配置：和 step1/step2 相同 ----------
ROOT = Path(__file__).resolve().parents[2]
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY")
if not API_KEY:
    sys.exit("缺少 NVIDIA_API_KEY，请在项目根目录配置 .env（参考 .env.example）")

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=API_KEY,
)

MODEL = "deepseek-ai/deepseek-v4.1-flash"


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
