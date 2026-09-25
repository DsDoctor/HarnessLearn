"""
llmkit.config —— 多提供方的配置与 client

为什么升级成多提供方（演进：单点故障的教训）：
  zenmux 直连不通、必须走本机代理 —— 代理一挂，整个项目就瘫了（实测发生过）。
  把"提供方"做成注册表之后：切换 = .env 里改一行 LLM_PROVIDER，
  不同提供方互为备份（走代理的挂了，就切直连的）。

.env 支持的变量（<P> = 提供方名大写，如 ZENMUX / NVIDIA）：
  LLM_PROVIDER     选填。当前用哪个提供方，默认 zenmux
  <P>_API_KEY      密钥（唯一必须放在 .env 的东西）
  <P>_MODEL        选填。不填用注册表里的默认模型
  <P>_BASE_URL     选填。不填用注册表里的默认地址
  <P>_PROXY        选填。不填用注册表里的默认代理（没写 = 直连）

新增一个提供方 = PROVIDERS 里加一条 + .env 里放它的密钥，其余代码一行不动。
"""

import os
import sys
from pathlib import Path

import httpx2 as httpx  # 本 venv 里 openai 底层的 httpx 分支就叫 httpx2（没有叫 httpx 的包）
from openai import OpenAI

# 项目根目录 = llmkit/ 的上一级
ROOT = Path(__file__).resolve().parents[1]


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


# 提供方注册表：每个提供方"固定的形状"写在这里（密钥除外 —— 密钥只放 .env）。
# proxy 没写 = 直连。这张表本身就是 step2 那句话的具象：
# "harness 里大量代码存在的意义，就是消化这种『兼容但不同』的现实。"
PROVIDERS = {
    "zenmux": {
        "base_url": "https://zenmux.ai/api/v1",
        "model": "z-ai/glm-5.3-flashx",
        "proxy": "http://127.0.0.1:7897",  # 直连不通，必须走本机代理
    },
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "model": "deepseek-ai/deepseek-v4.1-flash",
        # 不需要代理：国内直连可用 —— 代理挂了就切它
    },
}


def get_provider() -> str:
    """当前用哪个提供方（.env 里 LLM_PROVIDER 一行切换）。"""
    name = os.environ.get("LLM_PROVIDER", "zenmux")
    if name not in PROVIDERS:
        sys.exit(f"未知 LLM_PROVIDER={name!r}，可选：{' / '.join(PROVIDERS)}")
    return name


def get_client() -> OpenAI:
    """按当前提供方建 client：地址、代理、超时、重试都从这里进。"""
    name = get_provider()
    p = PROVIDERS[name]
    prefix = name.upper()  # zenmux → ZENMUX_API_KEY / ZENMUX_MODEL / ...

    api_key = os.environ.get(f"{prefix}_API_KEY", "")
    if not api_key or "你的密钥" in api_key or "粘贴" in api_key:
        sys.exit(f"{prefix}_API_KEY 还没配置：请打开项目根目录 .env 填入 {name} 的密钥")

    # 代理是每个提供方自己的事 —— 只挂在它自己的 client 上。
    # （旧做法写进 os.environ 全局生效，连 agent 工具起的子进程都会被带进代理）
    proxy = os.environ.get(f"{prefix}_PROXY", p.get("proxy"))
    http_client = httpx.Client(proxy=proxy) if proxy else None

    return OpenAI(
        base_url=os.environ.get(f"{prefix}_BASE_URL", p["base_url"]),
        api_key=api_key,
        http_client=http_client,  # None = 让 SDK 自己建（不需要代理的提供方）
        timeout=120,             # 现实教训：节点会挂，别等默认的 600 秒才报错
        max_retries=2,           # SDK 自带重试，扛住偶发抖动（ConnectTimeout 实测过）
    )


def get_model() -> str:
    """当前提供方用的模型（.env 里 <提供方>_MODEL 可覆盖默认）。"""
    name = get_provider()
    return os.environ.get(f"{name.upper()}_MODEL", PROVIDERS[name]["model"])
