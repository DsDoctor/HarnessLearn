"""
bare_call.py — 第 0 步：最简单的一次模型调用

在这个阶段，模型只是一个"函数"：
你发给它一串消息（messages），它返回一段文字。
没有记忆、没有工具、没有行动能力 —— 答完就忘。

但它是之后一切的原语（primitive）：
harness 再花哨，拆到最底下，仍然是这样一次调用。

运行：
    .venv/bin/python bare_call.py
"""

# os   —— 读取环境变量（API key 从这里来）
# sys  —— 出错时打印提示并退出程序
# Path —— 处理文件路径（比字符串拼接更安全清晰）
import os
import sys
from pathlib import Path

# openai 库本质上就是一个 HTTP 客户端。
# NVIDIA 的接口与 OpenAI"兼容"（请求/响应格式一模一样），
# 所以同一套客户端代码换个 base_url 就能连过去。
from openai import OpenAI


# ---------- 配置：从环境变量或 .env 文件读 API key ----------
def load_env() -> None:
    # .env 是一个纯文本文件，每行一条 KEY=VALUE。
    # 把它逐行读进环境变量；已存在的环境变量不会被覆盖（setdefault 的作用）。
    #
    # 为什么不直接写 api_key="$NVIDIA_API_KEY"？
    # 因为那是 Shell 的写法 —— 在 Python 里它只是一个字面字符串，
    # 并不会展开成环境变量的值。这是个非常常见的坑。
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
        "  export NVIDIA_API_KEY=nvda-xxx\n"
        "  或 cp .env.example .env 然后填入 key"
    )

# client 记住了两件事：请求发到哪（base_url）、用什么身份发（api_key），
# 这样后面每次调用都只需要写很短的一句。
# base_url 指向 NVIDIA 的服务，而不是 OpenAI 官方服务器。
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=API_KEY,
)


# ---------- 裸调用 ----------
# 下面这就是一次完整的"模型调用"，本质上是发了一个 HTTPS 请求。
completion = client.chat.completions.create(
    # 要调用的模型名，用的是你已经验证过能请求通的那个。
    model="deepseek-ai/deepseek-v4.1-flash",

    # messages 是模型能看到的"全部"输入 —— 就这一张列表，没有别的。
    # 这里用了两种角色：
    #   system —— 助手的"岗位说明书"，由开发者设定，模型全程遵守
    #   user   —— 用户实际问的问题
    # 以后这张列表会不断变长（追加 assistant 的回复、tool 的结果），
    # "变长的这张列表"就是 agent 的记忆。
    messages=[
        {"role": "system", "content": "你是一个乐于助人的助手。"},
        {"role": "user", "content": "9.11 和 9.8 哪个数字更大？"},
    ],

    # temperature（0 到 2）：输出的"随机程度"。
    # 越低越稳定，适合事实性问答；越高越发散，适合创意写作。
    temperature=0.5,

    # top_p：另一种采样控制（只在概率排名前 p 的候选词里挑）。
    # 经验法则：temperature 和 top_p 二选一调节即可。保持 1 相当于"不生效"。
    top_p=1,

    # max_tokens：回复长度的硬上限。一个汉字大约消耗 1~2 个 token。
    # 如果模型说到一半撞到上限，回答会被硬生生截断。
    max_tokens=1024,

    # stream=False：等模型全部生成完，一次性拿回完整回复。
    # stream=True 则边生成边一小块一小块地返回 ——
    # 聊天软件里"逐字打出"的效果就是这么实现的。
    stream=False,
)

# 返回值是一个层层嵌套的对象，真正的回答文本在这里取：
#     completion.choices[0].message.content
#   - choices         —— 一次请求可能返回多个候选回答，[0] 取第一个
#   - message.content —— 回答正文
#   - finish_reason   —— 模型为什么停笔：
#                          "stop"   = 正常说完
#                          "length" = 撞到 max_tokens 被截断
print("=== 完整的 message 对象（原始结构） ===")
print(completion.choices[0].message)

print("\n=== 只取回答正文（message.content） ===")
print(completion.choices[0].message.content)

print(f"\n=== 结束原因（finish_reason）: {completion.choices[0].finish_reason} ===")

# usage 是这次调用的 token 账单：
# prompt_tokens 是你发过去的内容，completion_tokens 是模型写回来的内容。
print(
    f"=== token 用量: 输入 {completion.usage.prompt_tokens} + "
    f"输出 {completion.usage.completion_tokens} = "
    f"共 {completion.usage.total_tokens} ==="
)

# reasoning_content（可选字段）：有些模型会"先想后说"（推理模型），
# 这个字段存的就是它的内心思考过程 —— 它不属于回答本身。
# 真正的回答永远是 message.content。
reasoning = getattr(completion.choices[0].message, "reasoning_content", None)
if reasoning:
    print("\n=== 思考过程（reasoning_content，前 200 字） ===")
    print(reasoning[:200] + "……")
