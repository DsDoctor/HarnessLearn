"""
llmkit.config —— 共用的配置与 client

为什么抽出来（演进：配置与代码分离）：
  每个 step 都要"读 .env → 建 client"，这段代码重复且没有学习价值。
  抽出来之后，换 API 节点只需要改 .env，所有 step 的代码一行不动。

.env 支持的变量：
  LLM_API_KEY   必填。密钥
  LLM_BASE_URL  选填。默认 https://zenmux.ai/api/v1
  LLM_MODEL     选填。默认 z-ai/glm-5.3-flashx
  LLM_PROXY     选填。HTTP 代理（zenmux 直连不通，要走本机代理）
"""

import os
import sys
from pathlib import Path

from openai import OpenAI

# 项目根目录 = llmkit/ 的上一级
ROOT = Path(__file__).resolve().parents[1]

DEFAULT_BASE_URL = "https://zenmux.ai/api/v1"
DEFAULT_MODEL = "z-ai/glm-5.3-flashx"


def load_env() -> None:
    """把项目根目录 .env 里的 KEY=VALUE 读进环境变量（已存在的不覆盖）。

    为什么不直接在代码里写 api_key="$XXX"？
    因为那是 Shell 的语法 —— 在 Python 里只是字面字符串，不会展开环境变量。
    """
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())


# import 这个模块时自动执行一次，之后所有函数都能读到配置
load_env()


def get_client() -> OpenAI:
    """校验配置并返回 client（base_url、代理都从这里进）。"""
    api_key = os.environ.get("LLM_API_KEY", "")

    # 防呆：占位符没替换就运行时，给一句人话提示，而不是让 API 返回看不懂的 403
    if not api_key or "粘贴" in api_key or "你的密钥" in api_key:
        sys.exit("LLM_API_KEY 还没配置：请打开项目根目录的 .env，把真实密钥粘进去")

    # zenmux 这类节点直连不通，要走本机代理 —— 代理也是配置的一部分
    proxy = os.environ.get("LLM_PROXY")
    if proxy:
        os.environ.setdefault("HTTPS_PROXY", proxy)
        os.environ.setdefault("HTTP_PROXY", proxy)

    return OpenAI(
        base_url=os.environ.get("LLM_BASE_URL", DEFAULT_BASE_URL),
        api_key=api_key,
    )


def get_model() -> str:
    """模型名也放进配置：换模型 = 改 .env，不改代码。"""
    return os.environ.get("LLM_MODEL", DEFAULT_MODEL)
