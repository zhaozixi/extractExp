# 标准库
import os, sys, json, datetime
# 本地向量数据库
try:
    import chromadb
except ImportError:
    print("❌ 缺少依赖 chromadb。", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    print("   请在当前环境中执行: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)
# 模型加载器（单例模式）
from model_loader import get_model

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
EXPS_DIR = os.path.join(BASE_DIR, 'exps')
# 向量数据库存储路径
VECTOR_DIR = os.path.join(EXPS_DIR, 'vector_store')
os.makedirs(VECTOR_DIR, exist_ok=True)

# 初始化 ChromaDB 持久化客户端（数据写入磁盘，重启不丢失）
client = chromadb.PersistentClient(path=VECTOR_DIR)
# 获取或创建集合，使用余弦相似度度量
collection = client.get_or_create_collection(
    name='experiences',
    metadata={"hnsw:space": "cosine"}
)
# 加载嵌入模型（单例，首次调用触发下载）
model = get_model()

def _deduplicate_graph(existing_graph, new_triples):
    """
    对知识图谱三元组进行去重合并。
    按 (source_id, head, relation, tail) 四元组作为唯一键，
    保留已有的，过滤掉同一经验内的重复三元组；
    不同经验(source_id 不同)即便三元组相同也视为不同条目，
    以保证 retriever.py 的图谱扩展与 deleter.py 的精准删除。

    Args:
        existing_graph: 已存在的三元组列表 [{head, relation, tail, source_id}, ...]
        new_triples: 新的三元组列表

    Returns:
        去重后的完整三元组列表
    """
    seen = set()       # 已见过的 (source_id, head, relation, tail) 键集合
    result = []        # 去重后的结果列表

    # 先处理已有图谱中的三元组
    for t in existing_graph:
        key = (t.get('source_id', ''),
               t.get('head', ''),
               t.get('relation', ''),
               t.get('tail', ''))
        if key not in seen:
            seen.add(key)
            result.append(t)

    # 再处理新三元组，跳过同一经验内的重复
    for t in new_triples:
        key = (t.get('source_id', ''),
               t.get('head', ''),
               t.get('relation', ''),
               t.get('tail', ''))
        if key not in seen:
            seen.add(key)
            result.append(t)

    return result

def save():
    """
    保存一条经验数据。
    从 stdin 读取 JSON，依次完成：
    1. 解析 JSON 输入
    2. 生成唯一 ID 和时间戳（缺失或 null 时自动生成）
    3. 规范化 level/timestamp/tags/entities 字段并写回 data
    4. 生成文本嵌入向量并存入 ChromaDB（exps/vector_store/）
    5. 自动关联相似经验（最近邻检索）
    6. 将完整数据写入 exps/ 下对应层级的 JSON 文件
    7. 更新 exps/graph.json 知识图谱（注入 source_id，按四元组去重追加）
    8. 返回保存结果（含经验 ID 和关联列表）
    """
    # ---------- 1. 读取并解析 stdin 中的 JSON ----------
    raw = sys.stdin.read()
    if not raw.strip():
        print(json.dumps({"status": "error", "message": "stdin 为空，未收到 JSON 数据"}, ensure_ascii=False))
        sys.exit(1)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"❌ JSON 格式错误: {e}", file=sys.stderr)
        sys.exit(1)

    # ---------- 2. 生成 ID 和时间戳 ----------
    # 若未指定 ID 或 ID 为显式 null，则使用当前时间作为唯一标识
    exp_id = data.get('id') or datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    data['id'] = exp_id
    # 规范化时间戳：保留已有值，缺失或显式 null 时生成新值，确保 JSON 文件与 ChromaDB 元数据一致
    data['timestamp'] = data.get('timestamp') or datetime.datetime.now().isoformat()

    # ---------- 3. 生成文本嵌入并写入向量库 ----------
    # 将场景、策略、元认知、标签拼接为嵌入文本（语义表示的载体）
    # 注意：使用 `or []` 而非 .get('标签', [])，以抵御 JSON 中显式 null 值
    # （.get 默认值仅在 key 缺失时生效，key 存在但值为 null 时仍返回 None）
    tags = data.get('标签') or []
    # 规范化 tags 并写回 data，确保 JSON 文件中该字段为有效列表而非 null
    data['标签'] = tags
    embed_text = (f"{data.get('场景') or ''} {data.get('策略') or ''} "
                  f"{data.get('元认知') or ''} {' '.join(tags)}")
    # 转为向量（Python list 格式，ChromaDB 要求）
    embedding = model.encode(embed_text).tolist()

    # 写入 ChromaDB 向量库
    try:
        collection.add(
            embeddings=[embedding],                          # 向量数据
            documents=[embed_text],                          # 原始文本（可用于检索时返回）
            metadatas=[{                                      # 元数据（用于过滤和展示）
                'level': data.get('level') or 'L1',          # 层级标识
                'tags': ','.join(tags)                       # 标签（逗号分隔）
            }],
            ids=[exp_id]                                      # 唯一 ID
        )
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        sys.exit(1)

    # ---------- 4. 自动关联相似经验 ----------
    # 以自身为 query 检索最近邻，找出最相似的 3 条经验建立关联
    related_ids = []
    try:
        neighbors = collection.query(query_embeddings=[embedding], n_results=4)
        # 取前 4 条（排除自身），最多保留 3 条关联
        if neighbors['ids'] and neighbors['ids'][0]:
            related_ids = [nid for nid in neighbors['ids'][0] if nid != exp_id][:3]
    except Exception as e:
        print(f"⚠️ 关联检索失败: {e}", file=sys.stderr)
    data['related'] = related_ids

    # ---------- 5. 将完整数据写入 JSON 文件 ----------
    # 根据 level 确定存储目录（使用 `or 'L1'` 防御显式 null）
    # 规范化 level 并写回 data，确保 JSON 文件中该字段为有效值而非 null
    level = data.get('level') or 'L1'
    data['level'] = level
    folder_map = {'L1': 'L1_Instances', 'L2': 'L2_Patterns', 'L3': 'L3_Principles'}
    folder = folder_map.get(level, 'L1_Instances')
    target_dir = os.path.join(EXPS_DIR, folder)
    os.makedirs(target_dir, exist_ok=True)

    # 以 ID 为文件名保存
    filepath = os.path.join(target_dir, f'{exp_id}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    # ---------- 6. 更新知识图谱 ----------
    # 将实体关系三元组追加到 graph.json（自动去重）
    # 规范化 entities 并写回 data，确保 JSON 文件中该字段为有效列表而非 null
    graph_data = data.get('entities') or []
    data['entities'] = graph_data
    graph_path = os.path.join(EXPS_DIR, 'graph.json')
    if graph_data:
        # 为每个三元组注入 source_id，使 retriever.py 能通过图谱扩展、
        # 使 deleter.py 能按经验 ID 清理对应的图谱引用
        graph_data = [dict(t, source_id=exp_id) for t in graph_data]

        # 读取已有图谱
        existing_graph = []
        if os.path.exists(graph_path):
            try:
                with open(graph_path, 'r', encoding='utf-8') as f:
                    existing_graph = json.load(f)
            except:
                pass  # 文件损坏则忽略，重建图谱

        # 去重合并后写回
        merged = _deduplicate_graph(existing_graph, graph_data)
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)

    # ---------- 7. 返回保存结果 ----------
    print(json.dumps({
        "status": "ok",
        "id": exp_id,
        "related": related_ids
    }, ensure_ascii=False))

if __name__ == '__main__':
    save()