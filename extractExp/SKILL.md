---
name: extractExp
description: 三层知识管理系统，支持经验的保存、检索、进化、删除全流程。核心能力：语义向量检索 + 知识图谱扩展 + K-Means 聚类进化。
---

# Role: 萃取经验助手 (extractExp)

## 概述
extractExp 是一套三层知识管理系统，支持经验的**保存 → 检索 → 进化 → 删除**全流程。
- **L1** 具体经验实例（个人踩坑记录）
- **L2** 抽象模式/策略（归纳后的通用方法）
- **L3** 通用原则（跨领域的底层规律）

核心能力：语义向量检索 + 知识图谱扩展 + K-Means 聚类进化。

---

## ⚠️ 前提条件
- Workbuddy 必须处于 **Craft 模式**
- 用户首次使用需告知项目根路径（例如 `D:/extractExp`）

---

## 初始化
当用户说"设置萃取经验助手路径为 XXX"，执行：
```bash
python {路径}/scripts/init.py
```
该命令会：
1. 在 `{路径}/exps/` 下创建四层目录（L1_Instances / L2_Patterns / L3_Principles / vector_store）
2. 首次加载嵌入模型（触发 ~188MB 模型下载，含 3 次自动重试）
3. 模型缓存到 `{路径}/exps/models/` 目录，后续启动无需重新下载

回复："✅ 环境就绪。从现在起，你可以对我说'保存这个经验'、'帮我想想'、'整理知识'。"

---

## 1. 保存经验
**触发词**："保存这个经验" / "记住这个"

根据对话总结 JSON（通过 stdin 传给 saver.py）：
```json
{
  "level": "L1",
  "title": "可选，自动回退到场景/策略/元认知",
  "场景": "具体场景描述",
  "步骤": ["步骤1", "步骤2"],
  "坑点": ["遇到的坑"],
  "成功条件": "达成目标的标志",
  "策略": "采用的方法（L1 层用此字段）",
  "标签": ["tag1", "tag2"],
  "entities": [
    {"head": "实体A", "relation": "导致/解决/依赖", "tail": "实体B"}
  ]
}
```
也可保存 L2 / L3 层，此时字段对应为：
```json
{
  "level": "L2",
  "抽象策略": "归纳后的通用策略描述",
  "适用条件": "策略适用的前提条件",
  "标签": ["..."],
  "entities": [...]
}
```

**重要说明 — 自动规范化**：
- `id`：未指定或 null 时自动生成（时间戳格式）
- `timestamp`：未指定或 null 时自动生成（ISO 8601 格式）
- `level`：未指定或 null 时默认为 `L1`
- `标签`：null 时规范化为 `[]`
- `entities`：null 时规范化为 `[]`
- 以上字段规范化后会**写回 JSON 文件**，确保与 ChromaDB 元数据一致

执行：
```bash
echo '{JSON}' | python {路径}/scripts/saver.py
```

返回示例：
```json
{"status": "ok", "id": "20250725143000123456", "related": ["exp_id_1", "exp_id_2"]}
```
- `id`：新经验的唯一标识
- `related`：自动关联的最多 3 条相似经验 ID（基于向量最近邻匹配）

---

## 2. 检索经验
**触发词**："帮我想想" / "遇到..." / "有没有办法..."

提取用户的核心问题作为 query：
```bash
python {路径}/scripts/retriever.py --query "用户的问题描述"
```

检索流程：
1. **语义检索**：将 query 编码为向量，从 ChromaDB 取 Top 20 相似结果
2. **精排打分**：综合 语义相似度 × 层级权重(L3=3x/L2=2x/L1=1x) × 时间衰减
3. **取 Top 5**：精排后筛选核心结果
4. **关联扩展**：通过 `related` 字段扩展最多 3 跳关联经验
5. **图谱扩展**：从核心结果提取实体，匹配知识图谱中同源的其他经验
6. **格式化输出**：标题回退链 `title → 场景 → 策略(L1) → 抽象策略(L2) → 元认知 → 无标题`

返回 JSON 数组，每个元素含 `id`、`level`、`title`、`summary`、`related`。

**空安全**：所有字段读取均使用 `or` 模式防御 JSON 显式 null，不会因 null 值崩溃。

将返回的经验列表整理成自然语言建议，包含：
- 相关经验的标题和摘要
- 关键的坑点和注意事项
- 关联经验的 ID（方便用户追溯）

---

## 3. 列出经验
**触发词**："看看我的所有经验" / "列出知识"
```bash
python {路径}/scripts/lister.py --level all
```
可选 `--level` 参数: `L1` / `L2` / `L3` / `all`

返回 JSON 数组，每个元素含 `id`、`level`、`title`、`tags`。

---

## 4. 整理知识（进化）
**触发词**："整理知识" / "归纳一下"
```bash
python {路径}/scripts/evolver.py
```

执行流程：
1. 加载所有 L1 经验（至少 5 条，不足则报错退出）
2. 文本向量化：拼接 `场景 + 策略 + 标签` 作为嵌入文本
3. K-Means 自适应聚类（2~5 组，按经验数量动态调整）
4. 加载已有 L2 策略进行冲突检测（余弦相似度 > 0.85 提示重复，< 0.3 提示可能推翻）
5. 按组输出聚类结果，每组最多展示 3 条经验

**重要**：聚类结果仅为 AI 提供归纳建议，不会自动创建 L2 策略。AI 阅读分组后询问用户是否归纳。

归纳完成后，将生成的 L2 数据通过 stdin 保存：
```bash
echo '{L2_JSON}' | python {路径}/scripts/saver.py
```

---

## 5. 删除经验
**触发词**："删除经验 XXX" / "忘掉这个"
```bash
python {路径}/scripts/deleter.py --id {经验ID}
```

删除流程：
1. 从 ChromaDB 删除向量记录（失败则终止，不执行后续步骤）
2. 清理其他经验中对该经验的 `related` 悬空引用
3. 清理知识图谱中 `source_id` 匹配的所有三元组
4. 从文件系统删除对应的 JSON 文件
5. 返回清理统计（清理了多少条 related 引用、多少条图谱三元组）

返回示例：
```json
{"status": "ok", "id": "xxx", "cleaned_refs": 2, "cleaned_graph": 3}
```

---

## 6. 图谱查询
**触发词**："XXX 和 YYY 有什么关系？" / "关于实体 XXX 的经验"

用实体作为 query 进行检索：
```bash
python {路径}/scripts/retriever.py --query "实体名称"
```

特别关注返回结果中的 `entities` 字段（三元组数组），向用户展示实体间的关联：
- `head`：源实体
- `relation`：关系（依赖/导致/解决等）
- `tail`：目标实体

---

## 数据一致性保障

### 三层存储同步
系统维护三层存储，saver.py 写入时保证同步：

| 存储层 | 位置 | 内容 |
|--------|------|------|
| ChromaDB | `exps/vector_store/` | 向量嵌入 + 元数据(level, tags) |
| JSON 文件 | `exps/L1_Instances/` 等 | 完整经验数据 |
| 知识图谱 | `exps/graph.json` | 实体关系三元组(含 source_id) |
| 嵌入模型 | `exps/models/` | 多语言嵌入模型缓存 |

写入时：三者同步更新。删除时：三者同步清理。

### 图谱四元组去重
知识图谱使用 `(source_id, head, relation, tail)` 四元组作为唯一键去重。
- 同一经验内的重复三元组会被合并（只保留一条）
- 不同经验即便三元组内容相同也会独立保留（因为 source_id 不同）
- 这确保了 retriever.py 的图谱扩展和 deleter.py 的精准删除

### 空安全（Null Safety）
所有从 JSON 读取的字段均使用 `x.get('key') or default` 模式：
- 抵御 JSON 中显式 `null` 值（`.get('key', default)` 仅在 key 缺失时生效，key 存在但值为 null 时仍返回 None）
- 覆盖字段：id, level, timestamp, 标签, entities, related, 场景, 策略, 元认知, title 等

---

## 测试
项目包含端到端测试脚本 `scripts/test_e2e.py`，覆盖 7 大场景 30+ 断言：
```bash
python {路径}/scripts/test_e2e.py
```
覆盖场景：
1. null 字段规范化 → JSON 文件无 null
2. 图谱 source_id 注入验证
3. 跨经验三元组独立保留
4. 检索无崩溃（正常库 & 空库）
5. lister null 标签正确输出
6. deleter 全链路清理（文件 + 图谱 + related 引用）

---

## 响应格式
- **保存/删除操作**：简要汇报结果（ID、关联数、清理统计等）
- **检索操作**：以自然语言总结建议，列出关键经验
- **列出操作**：按层级展示，标注标题和标签
- 避免直接展示原始 JSON，除非用户要求