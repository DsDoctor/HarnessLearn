"""
stream_call.py — 第 2 步：流式调用

和 step1 只有两处不同：
  ① stream=False 改成 True —— 返回值从"一个完整对象"变成"一个迭代器"
  ② 用 for 循环逐个接 chunk —— 每个 chunk 里的 delta 只是"增量"（几个字），
     完整回答要自己拼

详细解释见本目录 README.md。

运行（在项目根目录下）：
    .venv/bin/python steps/step2_streaming/stream_call.py
"""

import os
import sys
from pathlib import Path

from openai import OpenAI

# ---------- 配置：和 step1 相同 ----------
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

# ---------- 流式调用 ----------
stream = client.chat.completions.create(
    model="deepseek-ai/deepseek-v4.1-flash",
    messages=[
        {"role": "system", "content": "你是一个乐于助人的助手。"},
        {"role": "user", "content": "9.11 和 9.8 哪个数字更大？"},
    ],
    temperature=0.5,
    top_p=1,
    max_tokens=1024,
    stream=True,                                # ← 和 step1 唯一的参数差别
    stream_options={"include_usage": True},     # ← 让最后一个 chunk 带上 token 用量
)

# ---------- for 循环逐个接 chunk ----------
full_text = ""        # 正文要自己拼：模型只给增量，不帮你攒
reasoning_text = ""   # 思考流单独攒一份
n_chunks = 0
finish_reason = None
usage = None
hinted = False

print("=== 接收流：前 5 个 chunk 打印原始结构，之后直接逐字打印正文 ===\n")

for chunk in stream:
    n_chunks += 1
    # 坑：不是每个 chunk 都带这两个字段（缺了就不是 None，是直接抛 AttributeError）
    # 所以必须用 getattr 防御性取值
    delta = chunk.choices[0].delta
    reasoning_piece = getattr(delta, "reasoning_content", None)
    content_piece = getattr(delta, "content", None)

    # 前 5 个 chunk：展开看"增量"长什么样
    if n_chunks <= 5:
        print(f"[chunk {n_chunks}] {repr(delta)[:160]}")

    # 思考流：推理模型先流出思考，此时 content 还是 None，屏幕会安静一阵
    if reasoning_piece:
        reasoning_text += reasoning_piece
        if n_chunks > 5 and not hinted:
            print("（下面屏幕安静是正常的：模型在流式地思考，还没开始说……）")
            hinted = True

    # 正文流：逐字打印（打字机效果），同时手动拼装
    if content_piece:
        if n_chunks > 5:
            print(content_piece, end="", flush=True)   # end="" 不换行，flush=True 立刻刷屏
        full_text += content_piece

    # finish_reason 和 usage 都挂在最后一个 chunk 上
    if chunk.choices[0].finish_reason:
        finish_reason = chunk.choices[0].finish_reason
    if chunk.usage:
        usage = chunk.usage

print("\n\n=== 拼装完成的完整回答（自己用 += 攒出来的） ===")
print(full_text)

print("\n=== 统计 ===")
print(f"共 {n_chunks} 个 chunk；思考 {len(reasoning_text)} 字；正文 {len(full_text)} 字")
print(f"finish_reason: {finish_reason}")
if usage:
    print(
        f"token 用量: 输入 {usage.prompt_tokens} + "
        f"输出 {usage.completion_tokens} = 共 {usage.total_tokens}"
    )
