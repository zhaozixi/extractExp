# 标准库
import os, sys, json, argparse

# 项目根目录（scripts/ 的上一级）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 数据存储目录
EXPS_DIR = os.path.join(BASE_DIR, 'exps')

# 层级与目录的映射关系
LEVEL_DIRS = {
    'L1': 'L1_Instances',   # 具体经验实例
    'L2': 'L2_Patterns',    # 抽象模式/策略
    'L3': 'L3_Principles'   # 通用原则
}

def list_experiences(level='all'):
    """
    列出指定层级的所有经验。
    遍历对应目录下的 JSON 文件，提取 ID、标题、标签等关键信息。

    Args:
        level: 可选 'L1'/'L2'/'L3'/'all'，默认 'all' 列出全部

    Output:
        输出 JSON 数组到标准输出，每个元素包含 id/level/title/tags
    """
    result = []

    # 遍历三层目录
    for lvl, dirname in LEVEL_DIRS.items():
        # 如果指定了特定层级且不匹配则跳过
        if level != 'all' and lvl != level:
            continue

        dirpath = os.path.join(EXPS_DIR, dirname)
        if not os.path.exists(dirpath):
            continue

        # 读取该目录下所有 JSON 文件
        for fname in os.listdir(dirpath):
            if not fname.endswith('.json'):
                continue
            fpath = os.path.join(dirpath, fname)
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    rec = json.load(f)
                # 提取标题：优先 title，其次 场景/策略(L1)/抽象策略(L2)/元认知
                title = (rec.get('title')
                         or rec.get('场景')
                         or rec.get('策略')
                         or rec.get('抽象策略')
                         or rec.get('元认知')
                         or '无标题')
                result.append({
                    'id': rec.get('id') or fname[:-5],  # 优先使用 JSON 中的 id，null 时退化为文件名（去后缀）
                    'level': lvl,
                    'title': title,
                    # 使用 `or []` 防御 JSON 中显式 null
                    'tags': rec.get('标签') or []
                })
            except:
                # 单个文件解析失败不影响其他文件
                pass

    # 输出格式化 JSON 结果
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--level', default='all',
                        help='层级过滤: L1/L2/L3/all（默认 all）')
    args = parser.parse_args()
    list_experiences(args.level)