# 数据格式：v7 与 v8

这里的版本指主结果 `manifest.schema_version` / Zarr `result_schema_version`，不是 Python 包版本、Zarr 存储协议版本，也不是各 QA 的 `report_version`。代码当前 `RESULT_SCHEMA_VERSION=8`，Zarr 使用 v2；输入 manifest 与报告各自有独立版本。

v7 的所有字段完整保存 `1024³`。v8 仍在完整 `1024³` 上计算，共享原始梯度、
每尺度滤波速度和滤波梯度仅保存原网格 `[::2,::2,::2]`；起点为 0，
三个方向均取 `0,2,...,1022`，每 `2³` 个格点保留一个，存为覆盖整个周期域的 `512³`。
这是点值采样，不做块平均或插值。原始速度输入、Pi、S-bar、两个 Work 和 regime 保留全部格点。
所有导数、非线性乘积、统计和 QA 在完整计算网格上执行。
读取器接受 v7/v8；新写入和重建使用 v8，只有匹配 v8 格式的结果才参与计算复用。

## v8 布局和字段

```text
state_root/
  catalog.sqlite                       速度 tile 下载账本
  inputs/tNNNNNN/velocity_cache.zarr/velocity
  manifests/input_tNNNNNN.json          完整输入 manifest
  qa/input_tNNNNNN.json
result_root/
  tNNNNNN_shared_stride2/
    sampled_raw.zarr/gradient
    shared_manifest.json
    COMPLETE
  <result_id>/
    full_result_sigma_<tag>.zarr/
      velocity_bar, gradient_bar, work_full, work_resolved, pi, s_bar, regime
    shared_refs.json
    manifest.json
    qa.json, divergence.json, cq.json, weak_asymmetry.json, s_bar_qa.json
    COMPLETE
  .staging/                            尚未正式提交
  tNNNNNN_filter_*_batch_manifest.json
run_root/                              可重建的计算工作区
```

具体报告文件以 [函数索引](code_reference.md) 中的写入实现为准。`result_id` 由 `PipelineConfig.result_id()` 生成；Gaussian 与 smooth-sharp 分开，smooth-sharp 同时编码 alpha。`sigma_tag()` 使用 8 位有效数字，将小数点换为 `p`、负号换为 `m`；不要手工拼接近似参数名。

| 字段 | shape / axis order | dtype | 单位与含义 |
|---|---|---|---|
| velocity、velocity_bar | `(3,z,y,x)`；分量 x,y,z | little-endian float32 | 原速度与滤波速度 |
| gradient、gradient_bar | `(3,3,z,y,x)`；`[i,j]=∂_j u_i` | float32 | 原场与滤波场梯度 |
| work_full、work_resolved | `(z,y,x)` | float32 | 定义见 [实现说明](architecture.md) |
| pi、s_bar | `(z,y,x)` | float32 | `τ:∇ū`、SGS 传输散度 |
| regime | `(z,y,x)` | uint8 | 0 uncertain、1..6 六分区 |

其中 velocity 的空间维度为 `1024³`；gradient、velocity_bar、gradient_bar 为 `512³`；
四个标量场和 regime 为 `1024³`。`field_scopes` 对三个采样字段为 `full_domain_stride2`，
其余字段为 `full_domain`。逐字段 `field_sampling` 含 `origin_xyz`、`stride_xyz`、`shape_xyz`；
采样字段固定 origin `[0,0,0]`、stride `[2,2,2]`、shape `[512,512,512]`。
它表示存储坐标到原网格的映射，物理采样间距为 `2*domain_length/1024`。
GUI 速度对比会从完整原速度读取相同采样点，图轴和切片位置使用原网格 index。

每尺度未压缩 23 GiB：滤波速度 1.5 GiB、滤波梯度 4.5 GiB、四个标量 16 GiB、regime 1 GiB。
共享梯度每帧 4.5 GiB；输入速度每帧 12 GiB。五尺度永久数据共 131.5 GiB。
完整 FFT 临时缓存和计算工作区不因存储采样而缩小。

输入速度默认 chunks `(3,128,128,128)`；正式速度 chunks `(1,64,64,64)`，梯度 `(1,1,64,64,64)`，标量 `(64,64,64)`；小测试域使用 `min(64,n)`。压缩 Blosc zstd + BITSHUFFLE，level/threads 来自 YAML。NaN 为未填浮点字段，不能作为已完成数据。

`shared_refs.json` 保存 velocity store、shared gradient store、shared COMPLETE 的路径和 `input_manifest_hash`。当前写入绝对路径，迁移整个 result 文件夹仍可能依赖旧机器；参见 [系统迁移](system_migration.md)。不要脱离输入缓存和共享梯度复制单个 sigma。

`array_sha256` 对连续数组字节求 SHA-256；`hash_zarr_array` 按 chunk 顺序流式累计。因此逐字段 hash 不能简单用压缩文件 hash 或不同遍历顺序的全数组 hash 替代。读取器验证 COMPLETE、版本、共享输入 hash 和 shape；正式提交还会做有限值检查、字段 hash 和 QA。只有目录存在不等于结果有效。

## 从完整输入重建 v8

使用当前 YAML，指向原有完整 `state_root`。选择独立 result root，例如
`.local/results-rebuilt`，并按机器选 memory/memmap。

```bash
# 默认仅打印计划，不写数据、不发网络请求。
.venv-mac/bin/python scripts/rebuild_result.py --config configs/pipeline.macos.yaml --source-result /data/results/RESULT_ID --result-root /data/results-rebuilt
# 人工核对路径和资源后实际校验输入并重建；旧结果保持原样。
.venv-mac/bin/python scripts/rebuild_result.py --config configs/pipeline.macos.yaml --source-result /data/results/RESULT_ID --result-root /data/results-rebuilt --execute
```

Windows 将解释器换为 `.\.venv\Scripts\python.exe`，路径换成本机路径；Linux 用 `.venv-linux/bin/python`。脚本从源 manifest 获取 dataset、time、sigma、filter 与 alpha，拒绝未 COMPLETE 或非 v7/v8 来源。每次重建一个源结果，重复对其他 sigma 执行；批量高效方式是在新 YAML 中配置相同 sigma 列表后运行 `process-batch`。

结束后将本机配置 `result_root` 改为新目录，执行 `status`、GUI 和所需子项目统计。
block/QA 衍生结果使用新 result manifest 重新生成。跨机重建可用于绝对路径变化时恢复完整校验链。

## 压力与子项目格式

服务端梯度：`pressure_gradient_cache.zarr/pressure_gradient`，`(3,z,y,x)` float32，单独 `pressure_gradient_catalog.sqlite`、manifest/QA，method `fd4noint`。

本地 FD4：`pressure_cache.zarr/pressure` 为 `(z,y,x)` float32；`pressure_gradient_fd4_cache.zarr/pressure_gradient` 为 `(3,z,y,x)` float32。同帧目录内各自的 JSON manifest 保存块 checksum 和来源依赖。默认 FD4 block 64，halo 2，周期取模，float64 运算后写 float32；二者不共享服务端 catalog。`status --field pressure_gradient` 不报告这套本地 FD4 状态，应看本地 manifest。

QPower 支持 Zarr v2、NPY、NPZ，配置规定 key 和帧；统计 CSV、JSON 与图像定义见 [QPower README](../qpower_analysis/README.md)。其独立输出不使用主结果 schema。其余子项目格式由各自 README 负责。
