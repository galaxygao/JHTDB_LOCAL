# 数据格式：仅维护 v6 与 v7

这里的版本指主结果 `manifest.schema_version` / Zarr `result_schema_version`，不是 Python 包版本、Zarr 存储协议版本，也不是各 QA 的 `report_version`。代码当前 `RESULT_SCHEMA_VERSION=7`，Zarr 使用 v2；输入 manifest 与报告各自有独立版本，不能统一改成 7。

## 两版对照

v6 依据仓库原有 `HEAD` 的 config/store 实现核对；v7 依据当前工作区实现。v6 仅供识别与重建，不承诺当前 reader 直接读取。

| 项目 | v6 | v7 |
|---|---|---|
| 主 Zarr 名 | `center_result_sigma_<tag>.zarr` | `full_result_sigma_<tag>.zarr` |
| 空间域 | 速度/梯度仅中心 `[256:768)³`，其余物理场全域 | 所有逻辑场完整 `1024³` |
| `velocity` | 原始速度缓存的中心逻辑视图 | 直接引用完整输入速度缓存 |
| `gradient` | `tNNNNNN_shared/center_raw.zarr` 中心梯度 | `tNNNNNN_shared_full/full_raw.zarr` 完整梯度 |
| `velocity_bar` | `(3,512,512,512)` | `(3,1024,1024,1024)` |
| `gradient_bar` | `(3,3,512,512,512)` | `(3,3,1024,1024,1024)` |
| `work_full/work_resolved/pi/s_bar/regime` | 完整 `1024³` | 完整 `1024³` |
| `field_scopes` | `shared_center_crop/center_crop/full_domain` 混合 | 全部 `full_domain` |
| 升级方式 | 从完整已验证速度重新计算 | 同版本跨机可保留路径布局或重建 |

v6 中已丢弃裁剪外速度梯度与滤波速度，无法无损扩展为 v7。更新脚本执行物理重建，不插值、不补零、不篡改旧结果版本。文档维护窗口只包含这两版，不删除历史科学结果或 Git 历史。

## v7 布局和字段

```text
state_root/
  catalog.sqlite                       速度 tile 下载账本
  inputs/tNNNNNN/velocity_cache.zarr/velocity
  manifests/input_tNNNNNN.json          完整输入 manifest
  qa/input_tNNNNNN.json
result_root/
  tNNNNNN_shared_full/
    full_raw.zarr/gradient
    manifest.json
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

输入速度默认 chunks `(3,128,128,128)`；正式速度 chunks `(1,64,64,64)`，梯度 `(1,1,64,64,64)`，标量 `(64,64,64)`；小测试域使用 `min(64,n)`。压缩 Blosc zstd + BITSHUFFLE，level/threads 来自 YAML。NaN 为未填浮点字段，不能作为已完成数据。

`shared_refs.json` 保存 velocity store、shared gradient store、shared COMPLETE 的路径和 `input_manifest_hash`。当前写入绝对路径，迁移整个 result 文件夹仍可能依赖旧机器；参见 [系统迁移](system_migration.md)。不要脱离输入缓存和共享梯度复制单个 sigma。

`array_sha256` 对连续数组字节求 SHA-256；`hash_zarr_array` 按 chunk 顺序流式累计。因此逐字段 hash 不能简单用压缩文件 hash 或不同遍历顺序的全数组 hash 替代。读取器验证 COMPLETE、版本、共享输入 hash 和 shape；正式提交还会做有限值检查、字段 hash 和 QA。只有目录存在不等于结果有效。

## v6 → v7 更新脚本

先复制一份当前 v7 YAML，指向原有完整 `state_root`；不要给当前 loader 传带 `crop_start/crop_shape` 的旧 YAML。选择独立 result root，例如 `.local/results-v7`，并按机器选 memory/memmap。

```bash
# 默认仅打印计划，不写数据、不发网络请求。
.venv-mac/bin/python scripts/rebuild_v7.py --config configs/pipeline.macos.yaml --source-result /data/results-v6/RESULT_ID --result-root /data/results-v7
# 人工核对路径和资源后实际校验输入并重建；旧结果保持原样。
.venv-mac/bin/python scripts/rebuild_v7.py --config configs/pipeline.macos.yaml --source-result /data/results-v6/RESULT_ID --result-root /data/results-v7 --execute
```

Windows 将解释器换为 `.\.venv\Scripts\python.exe`，路径换成本机路径；Linux 用 `.venv-linux/bin/python`。脚本从旧 manifest 获取 dataset、time、sigma、filter 与 alpha，拒绝未 COMPLETE 或非 v6/v7 来源。每次重建一个源结果，重复对其他 sigma 执行；批量高效方式是在新 YAML 中配置相同 sigma 列表后运行 `process-batch`。

结束后将本机配置 `result_root` 改为新目录，执行 `status`、GUI 和所需子项目统计。v6 block/QA 衍生结果不直接改名复用，使用新 result manifest 重新生成。该工具也支持 v7→v7 跨机重建，用于绝对路径变化时恢复完整校验链。

## 压力与子项目格式

服务端梯度：`pressure_gradient_cache.zarr/pressure_gradient`，`(3,z,y,x)` float32，单独 `pressure_gradient_catalog.sqlite`、manifest/QA，method `fd4noint`。

本地 FD4：`pressure_cache.zarr/pressure` 为 `(z,y,x)` float32；`pressure_gradient_fd4_cache.zarr/pressure_gradient` 为 `(3,z,y,x)` float32。同帧目录内各自的 JSON manifest 保存块 checksum 和来源依赖。默认 FD4 block 64，halo 2，周期取模，float64 运算后写 float32；二者不共享服务端 catalog。`status --field pressure_gradient` 不报告这套本地 FD4 状态，应看本地 manifest。

QPower 支持 Zarr v2、NPY、NPZ，配置规定 key 和帧；统计 CSV、JSON 与图像定义见 [QPower README](../qpower_analysis/README.md)。其独立输出不是主结果 v6/v7。其余子项目格式由各自 README 负责。
