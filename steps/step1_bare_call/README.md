# 第 1 步：裸调用 —— 看懂一次完整的模型调用

**状态：✅ 已过关**

## 这一步是什么

模型在这个阶段只是一个"函数"：发给它一串消息（messages），它返回一段文字。
没有记忆、没有工具、没有行动能力 —— 答完就忘。

但它是之后一切的原语（primitive）：harness 再花哨，拆到最底下，仍然是这样一次调用。

```bash
# 运行（在项目根目录下）
.venv/bin/python steps/step1_bare_call/bare_call.py
```

## 配置去哪了？（llmkit 的由来）

初版 `bare_call.py` 里有一段"读 .env → 建 client"的配置代码。
你把第 1 步看懂之后，这段代码就没有学习价值了 —— 于是它被抽到
项目根目录的 `llmkit/` 包里，和 `steps/` 同级：

```python
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # 让脚本能找到 llmkit
from llmkit import get_client, get_model

client = get_client()   # 读 .env、校验密钥、配代理，一次搞定
MODEL = get_model()
```

这就是 harness 演进的常态：**看懂的部分变成地基，注意力留给新东西。**
顺带的红利：换 API 节点 / 换模型只需要改 `.env`，所有 step 的代码一行不动
（这次从 NVIDIA 换到 zenmux，三个 step 的代码就一行没改）。

## 概念速查表

| 概念 | 一句话理解 |
|---|---|
| `client` | 记住了"发给谁（base_url）+ 用什么身份（api_key）"，后面调用就不用重复写 |
| `messages` | 模型能看到的**全部**输入，就这一张列表，没有别的 |
| `role: system` | 助手的"岗位说明书"，由开发者设定 |
| `role: user` | 用户实际问的问题 |
| `temperature` | 随机程度：低→稳定事实，高→发散创意（0 到 2） |
| `top_p` | 另一种采样旋钮（只在概率前 p 的候选词里挑）；和 temperature 二选一调，1 = 不生效 |
| `max_tokens` | 回复长度硬上限；一个汉字约 1~2 个 token；撞到就截断 |
| `stream=False` | 等模型全部生成完，一次性拿回完整回复 |
| `choices[0].message.content` | 回答正文 |
| `finish_reason` | 模型为什么停笔：`stop`=说完，`length`=被截断 |
| `usage` | token 账单：输入多少（prompt_tokens）、输出多少（completion_tokens） |
| `reasoning_content` | 推理模型"先想后说"的思考过程，**不属于回答本身**；字段名各节点不同（NVIDIA 叫 `reasoning_content`，zenmux 叫 `reasoning`） |

## 两个坑

1. **API key 不要写死在代码里**：`api_key="$LLM_API_KEY"` 在 Python 里是**字面字符串**，
   不会展开环境变量（那是 Shell 的语法）。所以本项目统一从 `os.environ` 读取 + 可选 `.env` 文件
   （这件事已经由 `llmkit` 代劳了）。
2. **`.env` 不进 git**：`.gitignore` 已排除，`.env.example` 是模板。

## 为什么 messages 是理解 harness 的钥匙

`messages` 是模型能看到的**全部世界**。第 1 步里它只有两条（system + user），
但请记住这个视角：

- 多轮对话 = 不断往这张列表追加 `assistant`（模型的历史回复）和 `user`（新问题）
- agent = 再追加 `tool`（工具执行结果），并循环往复

**所谓 agent 的"记忆"，就是这张不断变长的列表。** 模型本身没有记忆——
它每次都是重新读完这张列表才开始回答的。

## 理解检查（已过关 ✅）

1. 模型一次请求能"看到"的全部东西是什么？
2. 把 `temperature` 从 0.5 调到 1.5，回答会怎么变？
3. `finish_reason` 显示 `"length"` 说明发生了什么？该调哪个参数？
4. `reasoning_content` 和 `content` 的区别是什么？

## 动手实验（可以随时回来做）

1. 把 user 消息换成你自己的问题，跑一遍
2. 把 `max_tokens` 改成 `10`，观察 `finish_reason` 变成 `length`、回答被拦腰截断
3. 把 `temperature` 改成 `0` 跑两次、再改成 `1.5` 跑两次，对比回答的波动
4. 每次运行注意最后的 token 用量 —— 这就是以后"上下文管理"要省的东西
