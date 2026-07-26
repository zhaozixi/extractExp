# 标准库
import os, sys, time
# 多语言文本嵌入模型（将文本转为向量用于语义搜索）
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("❌ 缺少依赖 sentence-transformers。", file=sys.stderr)
    print("   这通常不是没装依赖，而是用错了 Python 环境。", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    print("   请确认：", file=sys.stderr)
    print("   1. 你是否在正确的 Python 环境中运行了 pip install -r scripts/requirements.txt", file=sys.stderr)
    print("   2. 如果用了 Anaconda/虚拟环境，请先激活环境再运行脚本", file=sys.stderr)
    sys.exit(1)

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 设置模型缓存目录，首次下载后复用，避免重复联网下载
os.environ['SENTENCE_TRANSFORMERS_HOME'] = os.path.join(BASE_DIR, 'exps', 'models')
os.makedirs(os.environ['SENTENCE_TRANSFORMERS_HOME'], exist_ok=True)

# 全局单例模型，避免重复加载占用内存
_model = None

# HuggingFace 镜像列表（国内访问 huggingface.com 常超时）
_HF_MIRRORS = [
    'https://hf-mirror.com',
    'https://mirror.sjtu.edu.cn/huggingface',
]

def _try_load_model(model_name, endpoint=None):
    """
    尝试加载指定模型，可选指定 HF_ENDPOINT 镜像地址。
    调用后会恢复原先的 HF_ENDPOINT 环境变量，避免污染后续尝试。

    Returns:
        SentenceTransformer 实例，或 None 表示失败
    """
    # 保存原始 HF_ENDPOINT，避免切换端点时残留
    _original = os.environ.get('HF_ENDPOINT', '')
    try:
        if endpoint:
            os.environ['HF_ENDPOINT'] = endpoint
        elif 'HF_ENDPOINT' in os.environ:
            del os.environ['HF_ENDPOINT']
        model = SentenceTransformer(model_name)
        return model
    except Exception as e:
        print(f"    加载失败: {e}", file=sys.stderr)
        return None
    finally:
        # 恢复原始值
        if _original:
            os.environ['HF_ENDPOINT'] = _original
        elif 'HF_ENDPOINT' in os.environ:
            del os.environ['HF_ENDPOINT']

def get_model(max_retries=3):
    """
    获取多语言嵌入模型的单例实例。
    首次调用时自动下载 ~188MB 模型并缓存到 exps/models/ 目录；
    后续调用直接返回已加载的实例。
    支持自动切换 HuggingFace 镜像（解决国内连接超时问题）。

    Args:
        max_retries: 最大重试次数，默认 3 次

    Returns:
        SentenceTransformer 模型实例

    Raises:
        Exception: 所有镜像均加载失败时抛出
    """
    global _model
    # 已加载过则直接返回单例
    if _model is not None:
        return _model

    model_name = 'paraphrase-multilingual-MiniLM-L12-v2'

    # 优先尝试用户已设置的 HF_ENDPOINT
    user_endpoint = os.environ.get('HF_ENDPOINT', '').strip()
    if user_endpoint:
        print(f"检测到 HF_ENDPOINT={user_endpoint}，使用用户指定的镜像。", file=sys.stderr)
        for attempt in range(1, max_retries + 1):
            if attempt == 1:
                print("正在加载多语言嵌入模型...", file=sys.stderr)
            else:
                print(f"第 {attempt}/{max_retries} 次重试...", file=sys.stderr)
            result = _try_load_model(model_name, user_endpoint)
            if result:
                _model = result
                print("模型就绪。", file=sys.stderr)
                return _model
            if attempt < max_retries:
                time.sleep(attempt * 5)
    else:
        # 按顺序尝试：官网 → 镜像1 → 镜像2 → ...
        endpoints = [None] + _HF_MIRRORS  # None = 官网
        for idx, ep in enumerate(endpoints):
            label = "HuggingFace 官网" if ep is None else f"镜像 {ep}"
            print(f"尝试从 {label} 加载模型...", file=sys.stderr)

            for attempt in range(1, max_retries + 1):
                if attempt > 1:
                    print(f"  第 {attempt}/{max_retries} 次重试...", file=sys.stderr)
                result = _try_load_model(model_name, ep)
                if result:
                    _model = result
                    print(f"✅ 模型加载成功（来源: {label}）。", file=sys.stderr)
                    return _model
                if attempt < max_retries:
                    time.sleep(attempt * 5)

            # 当前端点失败，尝试下一个
            if idx < len(endpoints) - 1:
                print(f"  {label} 连接失败，切换到下一个源...", file=sys.stderr)
                time.sleep(2)

    # 所有端点都失败
    print(file=sys.stderr)
    print("❌ 模型加载失败，已尝试所有下载源。", file=sys.stderr)
    print("   可能原因：网络不通、所有镜像均不可用。", file=sys.stderr)
    print("   建议：", file=sys.stderr)
    print("   1. 检查网络连接", file=sys.stderr)
    print("   2. 手动设置镜像: set HF_ENDPOINT=https://hf-mirror.com", file=sys.stderr)
    print(f"   3. 确认磁盘空间充足（需约 200MB）", file=sys.stderr)
    print(f"   4. 缓存目录: {os.environ['SENTENCE_TRANSFORMERS_HOME']}", file=sys.stderr)
    raise Exception("模型加载失败，请检查网络或手动设置 HF_ENDPOINT 镜像后重试。")