# 第 2 步：流式调用 —— 分步看到模型是怎么"流"出来的

**状态：🎯 当前步骤**

## 为什么需要流式

模型生成文字本来就是**一个 token 一个 token**进行的。`stream=False` 是
"全部生成完再一次性返回"；`stream=True` 是"生成一点就推一点"。

HTTP 层面这叫 **SSE（Server-Sent Events）**：服务器不再发一个完整响应，
而是持续推送很多条 `data: {...}` 消息，直到结束。
聊天软件里"逐字打出回答"的效果就是这么实现的——首字等待时间大幅缩短。

```bash
# 运行（在项目根目录下）
.venv/bin/python steps/step2_streaming/stream_call.py
```

## 和 step1 的差别，其实只有两处

1. `stream=False` 改成 `True`（外加 `stream_options={"include_usage": True}` 请求 token 用量）
2. 返回值从"一个完整对象"变成"**一个迭代器**"，要用 for 循环逐个接 `chunk`

取值路径也随之变化：

| | step1 一次性 | step2 流式 |
|---|---|---|
| 返回值 | 一个 `ChatCompletion` 对象 | 一个能逐个吐 `chunk` 的迭代器 |
| 文本在哪 | `completion.choices[0].message.content` | 每个 `chunk.choices[0].delta.content` |
| 是完整的吗 | 是，就是完整回答 | **不是，只是增量（几个字）**，要自己拼 |
| `finish_reason` | 就在对象上 | 只在**最后一个 chunk** 上 |
| `usage` | 就在对象上 | 要传 `stream_options`，挂在最后一个 chunk |

## chunk 的解剖（本模型实测数据）

跑起来后前 5 个 chunk 会打印原始结构，长这样：

```
[chunk 1] ChoiceDelta(content=None, ..., role='assistant', ..., reasoning_content='我们需要')
[chunk 2] ChoiceDelta(content=None, ..., role=None, ..., reasoning_content='回答中文问题：“9.')
...
```

本次实测的一次完整流的节奏（每次运行数字会不同）：

| 阶段 | chunk 范围 | 特征 |
|---|---|---|
| 思考流 | 第 1 ~ 43 个 | `reasoning_content` 有增量，`content` 为 None |
| 转折点 | 第 44 个 | 最后一点思考尾巴 + 第一段正文，两者都有 |
| 正文流 | 第 45 ~ 50 个 | `content` 有增量，`reasoning_content` 消失 |
| 结束 | 最后一个 | `finish_reason='stop'` + `usage` 挂在上面 |

**所以推理模型的流式会先安静一阵（它在流式地"想"），然后才开始"说"。**

## 三个真实的坑（都是踩过的）

1. **增量必须自己拼**：接口不帮你攒，`full_text += delta.content` 就是全部秘密。
2. **字段可能整个缺失**：不是每个 chunk 都带 `content` / `reasoning_content` 字段。
   缺了不是给你 `None`，而是**直接抛 `AttributeError`**！
   所以必须用 `getattr(delta, "content", None)` 防御性取值——
   本脚本的第一个版本就在这里崩过。
3. **打字机效果靠 `end=""` + `flush=True`**：`print` 默认行缓冲（攒到换行才刷屏），
   不加 `flush=True` 的话，字会"憋很久后一次性蹦出来"，没有逐字效果。

## 这个 for 循环的"进化意义"

这是你在本项目遇到的**第一个循环**，值得多看两眼：

- step1：模型一次性给你结果 → 你拿到就是终点
- step2：模型持续给你数据流 → 你**逐段处理**，边收边用

第 3 步的 agent loop 是它的进阶版：模型不再持续给你"文字"，
而是给你"要做的事"（工具调用），你逐件执行、把结果喂回去、再要下一件。

## 理解检查

1. `stream=True` 时，`create()` 的返回值是什么类型？怎么从里面拿到回答文本？
2. `finish_reason` 和 `usage` 出现在哪个 chunk 上？怎么让它出现？
3. 打字机效果依赖 `print` 的哪两个参数？分别去掉会怎样？
4. 思考流和正文流在 chunk 里怎么区分？
5. 为什么取字段要用 `getattr` 而不能直接 `delta.content`？（想想哪个字段在哪些 chunk 上会缺失）

## 动手实验

1. **去掉 `flush=True`**：看打字机效果消失，字一次性蹦出来
2. **把打印改成 `print(repr(content_piece))`**：亲眼看每次只来几个字
3. **把"前 5 个"改成"前 50 个"**：感受思考流有多长、转折点在哪
4. **把思考流也逐字打出来**：提示——在 `if reasoning_piece:` 里加一个带前缀的打印，
   和正文用不同的标记区分
5. **数一数 chunk**：在统计里加"带正文的 chunk 有几个"，和总 chunk 数对比
