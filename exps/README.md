# exps 目录

extractExp 三层知识管理系统的数据存储目录。

## 目录结构

- **L1_Instances/** — 第一层：具体经验实例（个人踩坑记录）
- **L2_Patterns/** — 第二层：抽象模式/策略（归纳后的通用方法）
- **L3_Principles/** — 第三层：通用原则（跨领域的底层规律）
- **vector_store/** — ChromaDB 向量数据库存储
- **models/** — 嵌入模型缓存（首次运行 init.py 后自动下载）
- **graph.json** — 知识图谱三元组数据

## 初始化

首次使用前需运行 `scripts/init.py`，该脚本会自动创建以上子目录并下载嵌入模型（缓存到 `exps/models/`）。
