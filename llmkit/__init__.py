"""
llmkit —— 和 steps/ 同级的共用工具包

每一次演进沉淀出的可复用代码收在这里：
看懂的东西变成地基（这个包），注意力留给每个 step 的新东西。

v2：多提供方注册表 —— zenmux / nvidia 一行切换，代理按提供方独立配置。
"""

from llmkit.config import get_client, get_model, get_provider, load_env

__all__ = ["get_client", "get_model", "get_provider", "load_env"]
