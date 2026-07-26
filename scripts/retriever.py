# 标准库
import os, sys, json, argparse, datetime, math
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

# 初始化 ChromaDB 持久化客户端
client = chromadb.PersistentClient(path=VECTOR_DIR)
# 获取或创建集合，使用余弦相似度度量
collection = client.get_or_create_collection(
    name='experiences',
    metadata={"hnsw:space": "cosine"}
)
# 加载嵌入模型（单例）
model = get_model()

# ---------- ID → 文件路径 索引缓存 ----------
# 首次调用时从磁盘构建，后续直接查表，O(1) 替代 O(n²) 遍历
_id_path_cache = None

def _build_id_path_index():
    """
    扫描三层目录，构建 {经验ID: JSON文件路径} 的索引字典。
    用于快速定位经验记录，避免每次检索都遍历所有文件。

    Returns:
        dict: {经验ID: 文件绝对路径}
    """
    cache = {}
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        path = os.path.join(EXPS_DIR, folder)
        if not os.path.exists(path):
            continue
        for fname in os.listdir(path):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(path, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                # 优先使用 JSON 中的 id 字段，否则用文件名（去后缀）
                # 使用 `or` 防御 JSON 中显式 null，避免 null 污染缓存键
                exp_id = rec.get('id') or fname[:-5]
                cache[exp_id] = fpath
            except:
                # JSON 损坏时仍以文件名建立索引
                cache[fname[:-5]] = fpath
    return cache

def _get_record_path(exp_id):
    """
    根据经验 ID 获取对应的 JSON 文件路径。
    首次调用时自动构建索引缓存；如果缓存中找不到，
    则重建索引后重试（应对文件被新增/删除的情况）。

    Args:
        exp_id: 经验唯一 ID

    Returns:
        str or None: 文件绝对路径，找不到则返回 None
    """
    global _id_path_cache
    # 延迟初始化：首次调用时才构建缓存
    if _id_path_cache is None:
        _id_path_cache = _build_id_path_index()

    if exp_id in _id_path_cache:
        fpath = _id_path_cache[exp_id]
        # 文件确实存在则直接返回
        if os.path.exists(fpath):
            return fpath
        # 文件不存在（可能被删除），重建索引
        _id_path_cache = _build_id_path_index()

    # 重建后再次防御：若 cache 异常为 None（理论上不会，因 _build_id_path_index 总返回 dict），
    # 再重建一次以保证返回值不是 None
    if _id_path_cache is None:
        _id_path_cache = _build_id_path_index()
    # 若重建后仍找不到 exp_id，则返回 None（dict.get 默认）
    return _id_path_cache.get(exp_id)

def load_record_by_id(exp_id):
    """
    根据经验 ID 加载完整的经验记录（JSON 对象）。

    Args:
        exp_id: 经验唯一 ID

    Returns:
        dict or None: 经验数据字典，找不到或解析失败返回 None
    """
    fpath = _get_record_path(exp_id)
    if fpath and os.path.exists(fpath):
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    return None

def retrieve(query):
    """
    根据用户查询检索相关经验。
    检索流程：
    1. 将查询文本编码为向量
    2. 从 ChromaDB 获取 Top 20 语义相似结果
    3. 精排打分（综合语义、层级权重、时间衰减）
    4. 取 Top 5 结果
    5. 通过 related 字段扩展关联经验
    6. 通过知识图谱扩展实体相关经验
    7. 输出格式化的结果列表

    Args:
        query: 用户的问题描述文本

    Output:
        输出 JSON 数组到标准输出
    """
    # ---------- 1. 语义检索 ----------
    q_emb = model.encode(query).tolist()
    results = collection.query(query_embeddings=[q_emb], n_results=20)

    # 空结果守卫：向量库为空或无匹配时返回空数组
    if not results['ids'] or not results['ids'][0]:
        print(json.dumps([], ensure_ascii=False))
        return

    # ---------- 2. 精排打分 ----------
    # 考虑三个维度：语义相似度 × 层级权重 × 时间衰减
    scores = []
    now = datetime.datetime.now()

    for i, doc_id in enumerate(results['ids'][0]):
        rec = load_record_by_id(doc_id)
        if rec is None:
            continue  # JSON 文件丢失则跳过

        # 语义得分：ChromaDB 的余弦距离转换为 [0, 1] 分
        # ChromaDB cosine 空间下，距离 d ∈ [0, 2]，d=0 最相似，d=2 最不相似
        # 转换: score = 1 - d/2 ∈ [0, 1]
        dist_list = results.get('distances') or []
        cosine_dist = (dist_list[0][i]
                       if dist_list and dist_list[0] and i < len(dist_list[0])
                       else 1.0)
        semantic_score = 1 - (cosine_dist / 2)

        # 层级权重：L3(原则)=3x > L2(模式)=2x > L1(实例)=1x
        level_weight = {'L3': 3, 'L2': 2, 'L1': 1}.get(rec.get('level') or 'L1', 1)

        # 时间衰减：新经验权重更高，但不会完全遗忘旧经验
        # 公式: 1 / log2(age_days + 2)，age 越大权重越低
        try:
            ts = datetime.datetime.fromisoformat(rec.get('timestamp') or '')
            age_days = max(1, (now - ts).days)
            time_factor = 1 / math.log2(age_days + 2)
        except:
            time_factor = 0.5  # 无时间戳时给中等权重

        # 最终分数 = 语义 × 层级 × 时间
        final_score = semantic_score * level_weight * time_factor
        scores.append((doc_id, final_score))

    # 按最终分数降序排序
    scores.sort(key=lambda x: x[1], reverse=True)
    # 取 Top 5 作为核心结果
    top_ids = [s[0] for s in scores[:5]]

    # ---------- 3. 关联扩展（related 字段） ----------
    expanded = set(top_ids)
    for did in top_ids:
        rec = load_record_by_id(did)
        if rec:
            # 使用 `or []` 防御 JSON 中显式 null
            for rid in rec.get('related') or []:
                expanded.add(rid)

    # ---------- 4. 图谱扩展 ----------
    # 读取知识图谱，根据实体匹配扩展相关经验
    graph_path = os.path.join(EXPS_DIR, 'graph.json')
    if os.path.exists(graph_path):
        try:
            with open(graph_path, 'r', encoding='utf-8') as f:
                graph = json.load(f)
        except:
            graph = []

        # 从核心结果中提取所有实体（head 和 tail）
        matched_entities = set()
        for did in top_ids:
            rec = load_record_by_id(did)
            if rec:
                # 使用 `or []` 防御 JSON 中显式 null
                for ent in rec.get('entities') or []:
                    matched_entities.add(ent.get('head') or '')
                    matched_entities.add(ent.get('tail') or '')

        # 图谱中任一三元组的 head/tail 匹配时，将其 source_id 加入结果
        for triple in graph:
            if triple.get('head') in matched_entities or triple.get('tail') in matched_entities:
                src_id = triple.get('source_id')
                if src_id:
                    expanded.add(src_id)

    # ---------- 5. 输出结果 ----------
    output = []
    for did in expanded:
        rec = load_record_by_id(did)
        if rec:
            # 智能标题回退：title → 场景 → 策略(L1) / 抽象策略(L2) → 元认知 → 无标题
            title = (rec.get('title')
                     or rec.get('场景')
                     or rec.get('策略')
                     or rec.get('抽象策略')
                     or rec.get('元认知')
                     or '无标题')
            # 摘要：拼接场景 + 策略/抽象策略，取前 200 字符
            scene_text = (rec.get('场景') or '')
            strategy_text = (rec.get('策略') or rec.get('抽象策略') or '')
            summary = f"{scene_text} {strategy_text}".strip()
            if len(summary) > 200:
                summary = summary[:200] + '...'
            elif not summary:
                summary = '（无摘要）'
            output.append({
                'id': did,
                'level': rec.get('level'),
                'title': title,
                'summary': summary,
                # 使用 `or []` 防御 JSON 中显式 null
                'related': rec.get('related') or []
            })

    print(json.dumps(output, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--query', required=True,
                        help='用户的查询文本')
    args = parser.parse_args()
    retrieve(args.query)