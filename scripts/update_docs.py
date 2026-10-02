"""Generate AST-backed function and CLI references; --check detects stale docs/links."""
from __future__ import annotations
import argparse
import ast
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SUBPROJECTS = ('block_statistics', 'qpower_analysis', 'pi_pdf', 'pi_slices', 'scatter', 'regime_pi', 'flux_plateau')


def sources():
    paths = [ROOT / 'deploy.py', ROOT / 'dashboard.py']
    for folder in ('src/jhtdb_pipeline', 'scripts', *SUBPROJECTS):
        paths.extend(p for p in (ROOT / folder).rglob('*.py')
                     if not any(part in ('tests', 'output', '__pycache__', '.scratch', 'cache') for part in p.relative_to(ROOT).parts))
    return sorted(set(paths))


def link(path, destination, line=None):
    value = Path(os.path.relpath(path, destination.parent)).as_posix()
    return value + (f'#L{line}' if line else '')


def text(value):
    return str(value).replace('|', '\\|').replace('\n', ' ')


def symbols(tree):
    def walk(node, prefix=''):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                name = prefix + child.name
                yield name, child
                yield from walk(child, name + '.')
            else:
                yield from walk(child, prefix)
    return list(walk(tree))


def reference(paths, destination):
    out = ['# 逐函数代码参考', '', '由 `scripts/update_docs.py` 根据当前源码生成；不要手工编辑。包含私有函数、类和嵌套定义。签名中的默认值和类型来自源码；静态调用可能包含第三方库/回调，不等于完整动态调用图。实现细节沿源码链接阅读，科学语义见对应 README 与架构文档。', '']
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        rel = path.relative_to(ROOT)
        out += [f'## {rel}', '', f'[完整源码]({link(path, destination)})', '']
        imports = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
        if imports:
            out += ['依赖：', '', '```python', *imports, '```', '']
        constants = [ast.unparse(n) for n in tree.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
        if constants:
            out += ['模块常量/配置：', '', '```python', *constants, '```', '']
        definitions = symbols(tree)
        if not definitions:
            out += ['此入口只包含导入、常量或顶层调用。', '']
        for name, node in definitions:
            out += [f'### `{name}`', '', f'[实现：第 {node.lineno} 行]({link(path, destination, node.lineno)})', '']
            if isinstance(node, ast.ClassDef):
                signature = 'class ' + name + '(' + ', '.join(ast.unparse(b) for b in node.bases) + ')'
            else:
                signature = ('async ' if isinstance(node, ast.AsyncFunctionDef) else '') + 'def ' + name + '(' + ast.unparse(node.args) + ')'
                if node.returns:
                    signature += ' -> ' + ast.unparse(node.returns)
            out += ['```python', signature, '```', '']
            if isinstance(node, ast.ClassDef):
                fields = [ast.unparse(n) for n in node.body if isinstance(n, (ast.Assign, ast.AnnAssign))]
                if fields:
                    out += ['字段/默认值：', '', '```python', *fields, '```', '']
            doc = ast.get_docstring(node)
            if doc:
                out += [doc, '']
            if not isinstance(node, ast.ClassDef):
                calls = sorted({ast.unparse(n.func) for n in ast.walk(node) if isinstance(n, ast.Call)})
                raises = sorted({ast.unparse(n.exc) for n in ast.walk(node) if isinstance(n, ast.Raise) and n.exc})
                if calls: out += ['调用：' + ', '.join('`'+c+'`' for c in calls), '']
                if raises: out += ['显式异常：', '', '```python', *raises, '```', '']
    return '\n'.join(out)


def cli_reference(paths):
    out = ['# 全功能命令与参数参考', '', '全部命令从项目根目录运行，`python` 替换为本机虚拟环境解释器。以下 argparse 参数直接从代码生成，保留 default/type/choices/required/help；共用 helper 参数会在其所属模块列出。表达式默认值的实际值以配置/运行时 `--help` 为准。', '', '主入口：`python -m jhtdb_pipeline COMMAND --config CONFIG`。各命令及前后置条件见 [操作手册](handbook.md)。独立脚本用 `python 路径 --help`。PowerShell/bash 包装入口见 [scripts README](../scripts/README.md)。', '', '| 主命令 | 行为 |', '|---|---|', '| auth status | token 配置来源；不验证网络 |', '| doctor / plan | 环境、路径、资源 / 请求规划 |', '| smoke | 小型在线请求 |', '| cache / validate-input | 下载续传 / 本地完整校验 |', '| status | catalog 和正式结果状态；不包含本地 FD4 manifest |', '| process-full / finalize-result | 单尺度计算（或配置全部尺度）/显式提交 |', '| process-batch | 多尺度共享计算与提交 |', '| single-frame | 必要时 doctor、cache、validate、batch；完整结果可直接复用 |', '| compute-cq / compute-weak-asymmetry / qa-sbar | 重算或复用正式 QA 报告 |', '| compute-regime-pi | 独立逐 regime 输出 |', '| gui | 启动只读 Streamlit |', '', '`--sigma-grid` 与 `--sigma-grids` 互斥，后者仅 batch/single-frame/regime-pi 支持。滤波覆盖参数只作用于本次命令。主 CLI 通常成功 0，异常 1，doctor/QA 不通过 2；argparse 用法错误也为 2。', '']
    for path in paths:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
        calls = sorted([n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in ('add_argument', 'add_parser')], key=lambda n:n.lineno)
        if not calls: continue
        out += [f'## {path.relative_to(ROOT)}', '', f'[实现]({link(path, ROOT / "docs/cli_reference.md")})', '', '```python']
        out.extend(ast.get_source_segment(source, n) for n in calls)
        out += ['```', '']
    return '\n'.join(out)


def check_links():
    paths = [ROOT / 'README.md', *(ROOT / 'docs').glob('*.md'), ROOT / 'scripts/README.md', ROOT / 'src/jhtdb_pipeline/README.md']
    for folder in SUBPROJECTS:
        paths.extend((ROOT / folder).glob('*.md'))
    problems = []
    for path in paths:
        source = re.sub(r'```.*?```', '', path.read_text(encoding='utf-8'), flags=re.S)
        for raw in re.findall(r'\]\(([^)]+)\)', source):
            target = raw.split('#')[0]
            if not target or '://' in target or target.startswith('mailto:'): continue
            if not (path.parent / target).exists():
                problems.append(f'{path.relative_to(ROOT)}: missing {raw}')
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    paths = sources()
    core = [p for p in paths if p.relative_to(ROOT).parts[0] not in SUBPROJECTS]
    generated = {ROOT / 'docs/code_reference.md': reference(core, ROOT / 'docs/code_reference.md'),
                 ROOT / 'docs/cli_reference.md': cli_reference(paths)}
    for folder in SUBPROJECTS:
        destination = ROOT / folder / 'CODE_REFERENCE.md'
        generated[destination] = reference([p for p in paths if p.relative_to(ROOT).parts[0] == folder], destination)
    errors = []
    for path, content in generated.items():
        content += '\n'
        if args.check:
            if not path.exists() or path.read_text(encoding='utf-8') != content:
                errors.append(f'stale: {path.relative_to(ROOT)}')
        else:
            path.write_text(content, encoding='utf-8')
    errors += check_links()
    print('\n'.join(errors) if errors else f'OK: {len(paths)} Python sources; {len(generated)} generated references; local documentation links valid')
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
