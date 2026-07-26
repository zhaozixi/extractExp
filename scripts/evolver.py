# 标准库
import os, sys, json
# 数值计算
try:
    import numpy as np
except ImportError:
    print("❌ 缺少依赖 numpy。", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    print("   请在当前环境中执行: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)
# 机器学习聚类算法
try:
    from sklearn.cluster import KMeans
except ImportError:
    print("❌ 缺少依赖 scikit-learn。", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    print("   请在当前环境中执行: pip install -r scripts/requirements.txt", file=sys.stderr)
    sys.exit(1)
# 模型加载器（单例模式）
from model_loader import get_model

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
EXPS_DIR = os.path.join(BASE_DIR, 'exps')
# 加载嵌入模型（单例）
model = get_model()

def _load_l1_records():
    """
    从磁盘加载所有 L1 层（具体经验实例）的 JSON 记录。
    每次调用时重新扫描目录，确保获取最新数据。

    Returns:
        list[dict]: L1 经验记录列表
    """
    records = []
    folder = os.path.join(EXPS_DIR, 'L1_Instances')
    if not os.path.exists(folder):
        return records
    for fn in os.listdir(folder):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(folder, fn), 'r', encoding='utf-8') as f:
                records.append(json.load(f))
        except:
            pass  # 单个文件损坏不影响其他文件
    return records

def _load_l2_records():
    """
    从磁盘加载所有 L2 层（抽象模式/策略）的 JSON 记录。
    用于后续的冲突检测。

    Returns:
        list[dict]: L2 策略记录列表
    """
    records = []
    folder = os.path.join(EXPS_DIR, 'L2_Patterns')
    if not os.path.exists(folder):
        return records
    for fn in os.listdir(folder):
        if not fn.endswith('.json'):
            continue
        try:
            with open(os.path.join(folder, fn), 'r', encoding='utf-8') as f:
                records.append(json.load(f))
        except:
            pass
    return records

def _cosine_similarity(l2_embs, cluster_emb):
    """
    计算 L2 策略嵌入向量与聚类中心向量的余弦相似度。
    用于检测新发现的策略组与已有 L2 策略之间的冲突/重复关系。

    Args:
        l2_embs: 已有 L2 策略的嵌入矩阵，形状 (n, d) 或 (d,)
        cluster_emb: 当前聚类中心向量，形状 (d,)

    Returns:
        np.ndarray or None: 余弦相似度数组，长度为 L2 策略数量；
                            若维度不匹配则返回 None
    """
    # 确保 l2_embs 是 2D 矩阵
    if l2_embs.ndim == 1:
        l2_embs = l2_embs.reshape(1, -1)

    # 维度校验：确保 L2 嵌入和聚类中心的维度一致
    if l2_embs.shape[1] != cluster_emb.shape[0]:
        return None

    # 计算余弦相似度 = dot(a,b) / (|a| * |b|)
    cluster_norm = np.linalg.norm(cluster_emb)
    if cluster_norm < 1e-8:
        return np.zeros(l2_embs.shape[0])

    l2_norms = np.linalg.norm(l2_embs, axis=1)
    sims = np.dot(l2_embs, cluster_emb) / (l2_norms * cluster_norm + 1e-8)
    return sims

def evolve():
    """
    知识进化主函数。
    对 L1 经验进行 K-Means 聚类，发现潜在的策略组（L2 候选），
    并检测与已有 L2 策略的冲突关系。

    流程：
    1. 加载所有 L1 经验（需 ≥ 5 条）
    2. 将 L1 文本编码为向量
    3. K-Means 聚类为 2~5 组
    4. 加载已有 L2 策略用于冲突检测
    5. 对每个聚类组计算与已有 L2 的相似度
    6. 输出分组结果和冲突提示
    """
    # ---------- 1. 加载 L1 经验 ----------
    l1_records = _load_l1_records()
    if len(l1_records) < 5:
        print('❌ 经验不足（至少5条），无法聚类。', file=sys.stderr)
        return

    # ---------- 2. 文本向量化 ----------
    # 使用 `or ''` 统一 id 取值模式，防御 JSON 中显式 null
    ids = [r.get('id') or '' for r in l1_records]
    # 拼接场景 + 策略 + 标签作为嵌入文本（防御 null）
    texts = [(f"{r.get('场景') or ''} {r.get('策略') or ''} "
              f"{' '.join(r.get('标签') or [])}")
             for r in l1_records]
    emb = model.encode(texts)  # 形状 (n, d)

    # ---------- 3. K-Means 聚类 ----------
    # 聚类组数：最少 2 组，最多 5 组，按经验数量自适应
    n_clusters = min(5, max(2, len(ids) // 3))
    kmeans = KMeans(n_clusters=n_clusters, random_state=0, n_init=10).fit(emb)
    # 将 numpy 整型标签转为 Python 原生 int，避免 numpy>=2.0 下
    # int(numpy_int) / np.mean 列表混合类型等引发的 TypeError
    labels = [int(lb) for lb in kmeans.labels_]  # 每条 L1 经验所属的簇编号

    # 按簇分组
    clusters = {}
    for i, lb in enumerate(labels):
        clusters.setdefault(lb, []).append(l1_records[i])

    # ---------- 4. 加载已有 L2 策略（用于冲突检测） ----------
    existing_l2 = _load_l2_records()
    l2_embs = None
    if existing_l2:
        # 对 L2 的抽象策略和适用条件进行嵌入（防御 null）
        l2_texts = [f"{l.get('抽象策略') or ''} {l.get('适用条件') or ''}"
                    for l in existing_l2]
        l2_embs = model.encode(l2_texts)

    # ---------- 5. 输出聚类结果和冲突提示 ----------
    print(f'共发现 {len(clusters)} 个潜在策略组：\n')

    # 按簇编号排序输出
    unique_labels = sorted(set(labels))
    for lb in unique_labels:
        # 计算该簇的嵌入中心（所有成员嵌入的均值）
        # 先沿第 0 维堆叠成 (k, d) 矩阵，再按列求均值，避免 Python list 与
        # numpy array 混合传给 np.mean 产生的不可预期行为
        cluster_idx = [i for i, v in enumerate(labels) if v == lb]
        cluster_emb = np.mean(np.vstack([emb[i] for i in cluster_idx]), axis=0)

        # 冲突检测：与已有 L2 策略比较相似度
        conflict_msg = ''
        if l2_embs is not None and len(l2_embs) > 0:
            sims = _cosine_similarity(l2_embs, cluster_emb)
            if sims is not None and len(sims) > 0:
                max_sim = float(max(sims))
                if max_sim > 0.85:
                    # 高度相似 → 可能重复
                    conflict_msg = ' ⚠️ 高度相似 → 可能重复，建议合并或增加变体'
                elif max_sim < 0.3:
                    # 差异极大 → 可能推翻旧策略
                    conflict_msg = ' 🔄 差异较大 → 可能推翻旧策略，建议新建并标记旧策略为过期'

        items = clusters.get(int(lb), [])
        print(f'--- 组 {lb+1} (共{len(items)}条){conflict_msg} ---')
        # 每组最多展示 3 条经验的标题和场景
        for item in items[:3]:
            # 使用 `or` 防御 JSON 中显式 null，否则 None[:60] 抛 TypeError
            title = item.get('title') or '无标题'
            scene = (item.get('场景') or '')[:60]
            print(f"  · {title}: {scene}")
        print()

    # 提示 AI 进行归纳
    print('请 AI 阅读以上分组，询问用户是否归纳为新策略 (L2)。')

if __name__ == '__main__':
    evolve()