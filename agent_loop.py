"""
agent_loop.py — Stage 1：最简 Agent Loop（学完 bare_call.py 之后再来看这个）

一个 agent 的本质就是下面这个循环（伪代码）：

    while True:
        回复 = 模型(全部历史消息 messages)
        if 回复.要求调用工具:
            结果 = 执行工具(回复.工具调用)
            把结果追加进 messages        # 喂回给模型
        else:
            return 回复.内容             # 最终回答

相比 bare_call.py，只多了三样东西：
  1. 一个工具 run_bash          —— agent 的"手"，能对真实世界产生影响
  2. create() 多传 tools= 参数  —— 告诉模型它有这只手可用
  3. 一个循环                   —— 把"一次调用"变成"能干活的 agent"

关键认知：
  * messages 列表就是 agent 的全部记忆与状态。
    harness 里所有花哨概念（上下文管理、压缩、记忆），本质都是在管理这张列表。
  * 模型从不执行任何东西，它只输出"我想执行 X"。
    真正的执行永远发生在你自己的 Python 进程里 ——
    所以"权限 / 沙箱 / 审批"这些 harness 概念才会存在。
  * 循环只有两个出口：模型不再要工具（完成），或触发 max_turns（保险丝）。

运行：
    .venv/bin/python agent_loop.py                       # 默认演示问题
    .venv/bin/python agent_loop.py "帮我看看这个目录里有什么"
"""

import json
import os
import subprocess
import sys
from pathlib import Path

from openai import OpenAI


# ---------- 配置：从环境变量或 .env 文件读 API key ----------
def load_env() -> None:
    """把项目根目录 .env 里的 KEY=VALUE 读进环境变量（已存在的不覆盖）。"""
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


load_env()

API_KEY = os.environ.get("NVIDIA_API_KEY")
if not API_KEY:
    sys.exit(
        "缺少 NVIDIA_API_KEY。两种配法任选其一：\n"
        '  export NVIDIA_API_KEY=nvda-xxx\n'
        "  或 cp .env.example .env 然后填入 key"
    )

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=API_KEY,
)

MODEL = "deepseek-ai/deepseek-v4.1-flash"


# ---------- 工具：agent 的"手" ----------
def run_bash(command: str) -> str:
    """执行一条 shell 命令并返回输出。这是最经典的最小 agent 工具。"""
    try:
        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        output = (proc.stdout + proc.stderr).strip()
        return output or "(命令执行成功，无输出)"
    except subprocess.TimeoutExpired:
        return f"(命令超时：{command})"


# 工具注册表：名字 → Python 函数。
# 以后想加工具（读文件、写文件、搜索…），就是往这两个结构里各加一条。
TOOL_FUNCS = {"run_bash": run_bash}

# 给模型看的"工具说明书"（JSON Schema）。
# 模型只读这份描述来决定何时、如何调用，所以 description 写得越清楚，用得越准。
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
    """跑一轮完整的 agent 对话，返回最终回答。"""

    # messages 是 agent 的全部记忆：
    # 每一轮模型回复、每一次工具结果都追加在这里，下一轮原封不动发给模型。
    # 所谓"上下文"，就是这张不断变长的列表。
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
        # ---- 第 1 步：把全部历史发给模型 ----
        # 和 bare_call.py 完全相同的调用，只多传了 tools=TOOLS_SPEC
        completion = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS_SPEC,
            temperature=0.5,
            top_p=1,
            max_tokens=2048,  # 比裸调用给得宽裕些：工具调用 + 回答都要占 token
            stream=False,
        )
        msg = completion.choices[0].message

        # 顺带观察：每轮消耗的 token 在增长 —— 这就是以后要做"上下文管理"的原因
        if completion.usage:
            print(f"[turn {turn}] (本轮上下文共 {completion.usage.total_tokens} tokens)")

        # ---- 第 2 步：模型要求调用工具？----
        if msg.tool_calls:
            # 先把模型这条"我要调工具"的消息追加进历史
            messages.append(msg)
            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                args = json.loads(tool_call.function.arguments)
                print(f"[turn {turn}] 🔧 模型调用 {name}({args})")

                result = TOOL_FUNCS[name](**args)  # ← 真正的执行发生在这里
                print(f"[turn {turn}] 📄 工具返回: {result[:300]}")

                # 把工具结果以 role="tool" 喂回 messages —— 整个 loop 最关键的一步
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": result,
                    }
                )
            continue  # 带着工具结果，进入下一轮

        # ---- 第 3 步：模型不再要工具 → 这就是最终回答 ----
        print(f"[turn {turn}] 💬 模型给出最终回答")
        return msg.content or ""

    # 保险丝：防止模型无限循环调工具，烧光你的 token
    return "(达到 max_turns 上限，agent 没能给出最终回答)"


if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or (
        "看看当前目录里都有哪些文件，然后用 python 帮我验证一下 "
        "9.11 和 9.8 哪个数字更大。"
    )
    print(f"🙋 用户: {question}\n")
    answer = agent_loop(question)
    print(f"\n🤖 Agent: {answer}")
