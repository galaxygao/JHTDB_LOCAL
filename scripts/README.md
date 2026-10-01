# PowerShell 运行脚本

## `bootstrap_local.ps1`

创建 `.venv`，安装项目及测试依赖，编译源码并运行测试：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bootstrap_local.ps1
```

## `run_stage.ps1`

使用项目虚拟环境执行单帧生产入口：

```powershell
.\scripts\run_stage.ps1 -Stage single-frame -TimeIndex 1
```

可用 `-SigmaGrid 30` 只处理一个 sigma，`-Config` 指定其他 YAML。

## `run_smooth_sharp_full_pipeline.ps1`

当前比例 smooth-sharp 的一键全流程：

1. `single-frame` 断点完成多 sigma 的输入、计算、QA 和正式提交；
2. 生成 GUI 使用的逐 regime Pi 正反传输 JSON；
3. 逐 sigma 串行计算 block `SijSij/W_resolved/W_full/Pi`；
4. 生成按 `SijSij` 排序的 CSV 和 HTML；
5. 打印最终 pipeline status。

生产默认值：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1
```

自定义新时间帧：

```powershell
.\scripts\run_smooth_sharp_full_pipeline.ps1 `
  -TimeIndex 7 `
  -SigmaGrids 8,16,32,64 `
  -SharpEdgeWidthFraction 0.10 `
  -BlocksPerAxis 8
```

参数：

| 参数 | 默认 | 含义 |
|---|---:|---|
| `TimeIndex` | `1` | JHTDB stored time index，必须 >=1 |
| `SigmaGrids` | `10,15,30,55,75` | 唯一正 sigma 列表 |
| `SharpEdgeWidthFraction` | `0.1171875` | 比例宽度 `alpha=w/k_c` |
| `BlocksPerAxis` | `16` | 每轴 block 数，必须整除 1024 |
| `Config` | `configs/pipeline.yaml` | YAML 路径 |
| `OverwriteBlockStatistics` | false | 忽略有效 block 缓存并重算 |

完整 CLI 分阶段方式见根 README。
