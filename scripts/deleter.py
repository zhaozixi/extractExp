# 标准库
import os, sys, json, argparse
# 本地向量数据库
try:
    import chromadb
except ImportError:
    print("❌ 缺少依赖 chromadb。", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    print("   请在当前环境中执行: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
EXPS_DIR = os.path.join(BASE_DIR, 'exps')
# 向量数据库存储路径
VECTOR_DIR = os.path.join(EXPS_DIR, 'vector_store')

# 初始化 ChromaDB 持久化客户端
client = chromadb.PersistentClient(path=VECTOR_DIR)
# 获取或创建集合
collection = client.get_or_create_collection(
    name='experiences',
    metadata={"hnsw:space": "cosine"}
)

def _remove_related_refs(target_id):
    """
    在所有经验的 related 字段中移除对 target_id 的引用。
    当一条经验被删除后，其他经验中对它的关联引用会变成悬空指针，
    此函数负责清理这些引用，保持数据一致性。

    Args:
        target_id: 要删除的经验 ID

    Returns:
        int: 被清理的引用数量
    """
    updated_count = 0
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        path = os.path.join(EXPS_DIR, folder)
        if not os.path.exists(path):
            continue
        for fn in os.listdir(path):
            if not fn.endswith('.json'):
                continue
            fp = os.path.join(path, fn)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                # 如果该经验的 related 列表中包含 target_id
                # 使用 `or []` 防御 JSON 中显式 null（否则 `in None` 抛 TypeError）
                related = rec.get('related') or []
                if target_id in related:
                    # 过滤掉对 target_id 的引用
                    rec['related'] = [r for r in related if r != target_id]
                    # 写回更新后的 JSON
                    with open(fp, 'w', encoding='utf-8') as f:
                        json.dump(rec, f, ensure_ascii=False, indent=2)
                    updated_count += 1
            except:
                pass  # 单个文件失败不影响其他文件
    return updated_count

def _remove_graph_refs(target_id):
    """
    从知识图谱中移除所有 source_id 等于 target_id 的三元组。
    删除经验时同步清理图谱数据。

    Args:
        target_id: 要删除的经验 ID

    Returns:
        int: 被移除的图谱三元组数量
    """
    graph_path = os.path.join(EXPS_DIR, 'graph.json')
    if not os.path.exists(graph_path):
        return 0
    try:
        with open(graph_path, 'r', encoding='utf-8') as f:
            graph = json.load(f)
        # 过滤掉 source_id 匹配的三元组
        new_graph = [t for t in graph if t.get('source_id') != target_id]
        removed = len(graph) - len(new_graph)
        if removed > 0:
            with open(graph_path, 'w', encoding='utf-8') as f:
                json.dump(new_graph, f, ensure_ascii=False, indent=2)
        return removed
    except:
        return 0

def delete(exp_id):
    """
    删除一条经验数据。
    依次执行：
    1. 从 ChromaDB 向量库删除（如失败则终止）
    2. 清理其他经验中对该经验的 related 引用
    3. 清理知识图谱中属于该经验的三元组
    4. 从文件系统删除对应的 JSON 文件

    Args:
        exp_id: 要删除的经验 ID

    Output:
        输出 JSON 结果到标准输出，包含删除状态和清理统计
    """
    # ---------- 1. 删除向量库记录 ----------
    try:
        collection.delete(ids=[exp_id])
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False))
        return

    # ---------- 2. 清理 related 悬空引用 ----------
    updated_refs = _remove_related_refs(exp_id)

    # ---------- 3. 清理图谱数据 ----------
    removed_graph = _remove_graph_refs(exp_id)

    # ---------- 4. 删除 JSON 文件 ----------
    deleted = False
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        path = os.path.join(EXPS_DIR, folder)
        if os.path.exists(path):
            for fn in os.listdir(path):
                if fn.endswith('.json'):
                    fp = os.path.join(path, fn)
                    try:
                        with open(fp, 'r', encoding='utf-8') as f:
                            rec = json.load(f)
                        if (rec.get('id') or '') == exp_id:
                            os.remove(fp)
                            deleted = True
                    except:
                        pass

    # ---------- 5. 返回删除结果 ----------
    if deleted:
        result = {"status": "ok", "id": exp_id}
        if updated_refs > 0:
            result["cleaned_refs"] = updated_refs       # 清理了多少条 related 引用
        if removed_graph > 0:
            result["cleaned_graph"] = removed_graph     # 清理了多少条图谱三元组
        print(json.dumps(result, ensure_ascii=False))
    else:
        # JSON 文件可能已不存在，但向量已成功删除
        print(json.dumps({"status": "warning", "message": "JSON未找到，但向量已删除"}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--id', required=True,
                        help='要删除的经验 ID')
    args = parser.parse_args()
    delete(args.id)