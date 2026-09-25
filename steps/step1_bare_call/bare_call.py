"""
bare_call.py — 第 1 步：最简单的一次模型调用

模型只是一个"函数"：发给它一串消息（messages），它返回一段文字。
没有记忆、没有工具、没有行动能力 —— 答完就忘。
详细解释见本目录 README.md。

运行（在项目根目录下）：
    .venv/bin/python steps/step1_bare_call/bare_call.py
"""

import os
import sys
from pathlib import Path

from openai import OpenAI

# ---------- 配置：从项目根目录的 .env 读 API key ----------
ROOT = Path(__file__).resolve().parents[2]   # steps/step1_bare_call/ 往上三级是项目根
env_file = ROOT / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if line.strip() and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

API_KEY = os.environ.get("NVIDIA_API_KEY")
if not API_KEY:
    sys.exit("缺少 NVIDIA_API_KEY，请在项目根目录配置 .env（参考 .env.example）")

# client 记住"发给谁（base_url）+ 用什么身份（api_key）"
client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=API_KEY,
)

# ---------- 裸调用：本质是发一个 HTTPS 请求 ----------
completion = client.chat.completions.create(
    model="deepseek-ai/deepseek-v4.1-flash",
    # messages 是模型能看到的"全部"输入：
    #   system = 岗位说明书（开发者设定）  user = 用户的问题
    # 以后这张列表会不断变长 —— "变长的列表"就是 agent 的记忆
    messages=[
        {"role": "system", "content": "你是一个乐于助人的助手。"},
        {"role": "user", "content": "9.11 和 9.8 哪个数字更大？"},
    ],
    temperature=0.5,   # 随机程度：低→稳定，高→发散
    top_p=1,           # 另一种采样旋钮，和 temperature 二选一调即可，1=不生效
    max_tokens=1024,   # 回复长度硬上限，撞到就截断（finish_reason 会变成 "length"）
    stream=False,      # False=等全部生成完一次性返回
)

# 回答正文在 completion.choices[0].message.content
# finish_reason: "stop"=正常说完  "length"=被 max_tokens 截断
print("=== 完整的 message 对象（原始结构） ===")
print(completion.choices[0].message)

print("\n=== 只取回答正文（message.content） ===")
print(completion.choices[0].message.content)

print(f"\n=== 结束原因（finish_reason）: {completion.choices[0].finish_reason} ===")

# token 账单：输入多少、输出多少
print(
    f"=== token 用量: 输入 {completion.usage.prompt_tokens} + "
    f"输出 {completion.usage.completion_tokens} = "
    f"共 {completion.usage.total_tokens} ==="
)

# 推理模型会"先想后说"：reasoning_content 是思考过程，不属于回答本身
reasoning = getattr(completion.choices[0].message, "reasoning_content", None)
if reasoning:
    print("\n=== 思考过程（reasoning_content，前 200 字） ===")
    print(reasoning[:200] + "……")
