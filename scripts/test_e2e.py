"""
端到端测试脚本：验证 null 安全修复及数据一致性。

覆盖场景：
1. 含 null 字段的 JSON → saver.py 保存 → 确认 JSON 文件字段已规范化
2. 含 null 字段的 JSON → 保存多条 → 确认图谱跨经验三元组独立保留
3. 空标签/空 entities → 保存 → 确认无崩溃
4. retriever.py 检索空库 → 确认返回空数组
5. deleter.py 删除 → 确认图谱、related、文件均清理
6. lister.py 列出 → 确认 null 标签输出为 []

运行方式：
    python scripts/test_e2e.py
依赖：已执行 init.py 且模型已下载
"""
import os
import sys
import json
import shutil
import tempfile
import subprocess

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SCRIPTS_DIR)
EXPS_DIR = os.path.join(BASE_DIR, 'exps')
PASS = 0
FAIL = 0


def check(desc, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ✅ {desc}")
    else:
        FAIL += 1
        print(f"  ❌ {desc}")


def run_py(script, *args, stdin_text=None):
    """调用本项目内的 Python 脚本，返回 (returncode, stdout, stderr)"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script)] + list(args)
    result = subprocess.run(
        cmd, input=stdin_text, capture_output=True, text=True, cwd=SCRIPTS_DIR
    )
    return result.returncode, result.stdout, result.stderr


def safe_remove_dir(path):
    if os.path.exists(path):
        shutil.rmtree(path, ignore_errors=True)


def main():
    global PASS, FAIL
    print("=" * 60)
    print("extractExp 端到端验证")
    print("=" * 60)

    # 清理并重建测试环境
    for d in ['L1_Instances', 'L2_Patterns', 'L3_Principles', 'vector_store']:
        safe_remove_dir(os.path.join(EXPS_DIR, d))
    for f in ['graph.json']:
        p = os.path.join(EXPS_DIR, f)
        if os.path.exists(p):
            os.remove(p)

    # ---------- 测试 1: null 字段规范化 ----------
    print("\n[1] null 字段规范化测试")
    payload = {
        "level": None,
        "title": "测试-null字段",
        "场景": None,
        "策略": None,
        "元认知": None,
        "标签": None,
        "entities": None,
        "timestamp": None
    }
    rc, out, err = run_py('saver.py', stdin_text=json.dumps(payload, ensure_ascii=False))
    check("saver.py 不崩溃", rc == 0)
    result = json.loads(out)
    check("保存返回 ok", result.get('status') == 'ok')
    exp_id = result['id']

    # 读取写入的 JSON 文件
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        fpath = os.path.join(EXPS_DIR, folder, f'{exp_id}.json')
        if os.path.exists(fpath):
            with open(fpath, 'r', encoding='utf-8') as f:
                saved = json.load(f)
            check("JSON 文件存在", True)
            check("level 已规范化为 L1", saved.get('level') == 'L1')
            check("timestamp 非空", bool(saved.get('timestamp')))
            check("标签为列表", isinstance(saved.get('标签'), list))
            check("entities 为列表", isinstance(saved.get('entities'), list))
            check("场景非 null", saved.get('场景') is not None)
            check("策略非 null", saved.get('策略') is not None)
            break
    else:
        check("JSON 文件存在", False)

    # ---------- 测试 2: 图谱 source_id 注入 ----------
    print("\n[2] 图谱 source_id 注入测试")
    with open(os.path.join(EXPS_DIR, 'graph.json'), 'r', encoding='utf-8') as f:
        graph = json.load(f)
    check("graph.json 存在", True)
    check("图谱是列表", isinstance(graph, list))
    if graph:
        triple = graph[0]
        check("三元组有 source_id", triple.get('source_id') == exp_id)

    # ---------- 测试 3: 跨经验三元组独立保留 ----------
    print("\n[3] 跨经验三元组独立保留测试")
    # 保存第二条经验，共享相同的实体关系
    payload2 = {
        "level": "L2",
        "title": "测试-跨经验",
        "场景": "场景B",
        "策略": "策略B",
        "标签": ["tag2"],
        "entities": [
            {"head": "React", "relation": "依赖", "tail": "Webpack"}
        ]
    }
    rc2, out2, _ = run_py('saver.py', stdin_text=json.dumps(payload2, ensure_ascii=False))
    check("第二条保存成功", rc2 == 0)
    result2 = json.loads(out2)
    exp_id2 = result2['id']

    with open(os.path.join(EXPS_DIR, 'graph.json'), 'r', encoding='utf-8') as f:
        graph = json.load(f)
    # 应该有 2 条三元组（两条经验各一条），而不是被合并为 1 条
    same_relation = [t for t in graph
                     if t.get('head') == 'React' and t.get('tail') == 'Webpack']
    check("跨经验三元组独立保留", len(same_relation) == 2)
    check("两条三元组 source_id 不同",
          same_relation[0].get('source_id') != same_relation[1].get('source_id'))

    # ---------- 测试 4: 检索无崩溃 ----------
    print("\n[4] 检索无崩溃测试")
    rc3, out3, err3 = run_py('retriever.py', '--query', '测试')
    check("retriever 不崩溃", rc3 == 0)
    try:
        results = json.loads(out3)
        check("检索返回列表", isinstance(results, list))
        check("至少有 1 条结果", len(results) >= 1)
        if results:
            item = results[0]
            check("结果有 id", bool(item.get('id')))
            check("结果有 title", bool(item.get('title')))
            check("结果 related 是列表", isinstance(item.get('related'), list))
    except Exception as e:
        check("检索返回有效 JSON", False)
        print(f"        解析错误: {e}")

    # ---------- 测试 5: 空库检索 ----------
    print("\n[5] 空库检索测试（先清理后验证）")
    # 创建临时干净环境
    for d in ['L1_Instances', 'L2_Patterns', 'L3_Principles', 'vector_store']:
        safe_remove_dir(os.path.join(EXPS_DIR, d))
    if os.path.exists(os.path.join(EXPS_DIR, 'graph.json')):
        os.remove(os.path.join(EXPS_DIR, 'graph.json'))
    # 重新初始化（不下载模型）
    rc4, out4, err4 = run_py('retriever.py', '--query', '任何')
    check("空库检索不崩溃", rc4 == 0)
    check("空库返回 []", out4.strip() == '[]')

    # ---------- 测试 6: lister null 标签 ----------
    print("\n[6] lister null 标签测试")
    # 先保存一条带 null 标签的记录
    payload3 = {
        "level": "L1",
        "title": "lister测试",
        "场景": "场景C",
        "标签": None
    }
    rc5, out5, _ = run_py('saver.py', stdin_text=json.dumps(payload3, ensure_ascii=False))
    check("保存成功", rc5 == 0)
    exp_id3 = json.loads(out5)['id']

    rc6, out6, _ = run_py('lister.py', '--level', 'L1')
    check("lister 不崩溃", rc6 == 0)
    listings = json.loads(out6)
    # 找到我们的记录，确认 tags 是列表而非 null
    target = [x for x in listings if x.get('id') == exp_id3]
    if target:
        check("lister 找到记录", True)
        check("tags 字段是列表", isinstance(target[0].get('tags'), list))
    else:
        check("lister 找到记录", False)

    # ---------- 测试 7: deleter 清理 ----------
    print("\n[7] deleter 清理测试")
    rc7, out7, _ = run_py('deleter.py', '--id', exp_id3)
    check("deleter 不崩溃", rc7 == 0)
    del_result = json.loads(out7)
    check("删除返回 ok", del_result.get('status') == 'ok')

    # 验证 JSON 文件已删除
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        fpath = os.path.join(EXPS_DIR, folder, f'{exp_id3}.json')
        if os.path.exists(fpath):
            check("JSON 文件已删除", False)
            break
    else:
        check("JSON 文件已删除", True)

    # 验证图谱 source_id 清理
    if os.path.exists(os.path.join(EXPS_DIR, 'graph.json')):
        with open(os.path.join(EXPS_DIR, 'graph.json'), 'r', encoding='utf-8') as f:
            g = json.load(f)
        remaining = [t for t in g if t.get('source_id') == exp_id3]
        check("图谱已清理对应 source_id", len(remaining) == 0)

    # 验证 related 引用清理（在其他经验中不应再引用 exp_id3）
    for folder in ['L1_Instances', 'L2_Patterns', 'L3_Principles']:
        dirpath = os.path.join(EXPS_DIR, folder)
        if not os.path.exists(dirpath):
            continue
        for fn in os.listdir(dirpath):
            if not fn.endswith('.json'):
                continue
            with open(os.path.join(dirpath, fn), 'r', encoding='utf-8') as f:
                rec = json.load(f)
            if exp_id3 in (rec.get('related') or []):
                check("related 引用已清理", False)
                break
        else:
            continue
        break
    else:
        check("related 引用已清理", True)

    # ---------- 汇总 ----------
    print("\n" + "=" * 60)
    total = PASS + FAIL
    print(f"通过: {PASS}/{total}  失败: {FAIL}/{total}")
    if FAIL == 0:
        print("🎉 全部通过！")
    else:
        print(f"⚠️  有 {FAIL} 项失败，请检查上方输出")
    print("=" * 60)
    sys.exit(0 if FAIL == 0 else 1)


if __name__ == '__main__':
    main()