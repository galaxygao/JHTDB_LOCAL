# 文档和目录维护

仓库保留主 pipeline 与 QPower 两个 pipeline。根 README 提供平台运行与导航，docs 维护共同实现、配置、迁移和当前数据格式；QPower 在自己的目录维护分析、测试和结果。历史结果的 provenance 保留原样。

## 文档索引

```bash
.venv-mac/bin/python scripts/update_docs.py
.venv-mac/bin/python scripts/update_docs.py --check
```

生成器通过 AST 生成主库和 QPower 的函数与 CLI 参数参考，检查本地文档链接，不下载数据。人工操作说明与公式也应同步维护。新结果写入 v9，读取兼容 v7/v8/v9；结果格式和 QA 报告版本分别管理。

## 验证

```bash
.venv-mac/bin/python -m pytest tests qpower_analysis/tests -q
```

Windows 和 Linux 使用本机虚拟环境解释器。合成测试不需要真实 token；在线 smoke、真实 1024³ 资源与目标系统实测另行执行。平台脚本见 [scripts README](../scripts/README.md)。
