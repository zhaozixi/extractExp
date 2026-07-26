# 标准库
import os, sys

# 预检：检查关键依赖是否已安装
def _check_dependencies():
    """
    启动前检查核心依赖是否可用，避免运行时才报错。
    返回 (ok, missing_list)
    """
    required = ['sentence_transformers', 'chromadb', 'sklearn']
    missing = []
    for dep in required:
        try:
            __import__(dep)
        except ImportError:
            missing.append(dep)
    return len(missing) == 0, missing

# 模型加载器（单例模式加载嵌入模型）
from model_loader import get_model

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
EXPS_DIR = os.path.join(BASE_DIR, 'exps')

def init():
    """
    初始化 extractExp 项目。
    在项目根目录的 exps/ 下创建三层知识目录（L1/L2/L3）和向量库目录，
    首次加载嵌入模型（触发 ~188MB 模型下载，缓存到 exps/models/）。
    """
    print("🔍 预检 Python 环境...", file=sys.stderr)
    print(f"   当前 Python: {sys.executable}", file=sys.stderr)
    ok, missing = _check_dependencies()
    if not ok:
        print(f"❌ 缺少依赖: {', '.join(missing)}", file=sys.stderr)
        print("   这通常不是没装依赖，而是用错了 Python 环境。", file=sys.stderr)
        print("   请确认：", file=sys.stderr)
        print("   1. 在当前 Python 环境中执行: pip install -r scripts/requirements.txt", file=sys.stderr)
        print("   2. 如果用了 Anaconda/虚拟环境，请先激活环境", file=sys.stderr)
        print("   3. 可运行 scripts/install.bat 自动查找 Python 并安装依赖", file=sys.stderr)
        sys.exit(1)
    print("   ✅ 依赖检查通过", file=sys.stderr)
    print(file=sys.stderr)

    # 需要创建的子目录列表
    dirs_to_create = [
        'L1_Instances',   # 第一层：具体经验实例
        'L2_Patterns',    # 第二层：抽象模式/策略
        'L3_Principles',  # 第三层：通用原则
        'vector_store'    # ChromaDB 向量数据库存储目录
    ]

    # 逐个创建目录（已存在则跳过）
    for sub in dirs_to_create:
        path = os.path.join(EXPS_DIR, sub)
        os.makedirs(path, exist_ok=True)
        print(f"📁 目录已创建: {sub}", file=sys.stderr)

    # 首次加载嵌入模型（会自动下载约 188MB，缓存到 exps/models/）
    print(file=sys.stderr)
    get_model()

    print(file=sys.stderr)
    print("🎉 初始化完成！现在可以对 AI 说\"保存这个经验\"了。", file=sys.stderr)
    print(f"   数据目录: {EXPS_DIR}", file=sys.stderr)

if __name__ == '__main__':
    init()