# 实现、科学约定与接手指南

## 系统边界

主库 `src/jhtdb_pipeline` 提供配置、鉴权、下载、缓存、谱运算、正式提交、QA 与 GUI。根 `deploy.py` 是跨平台环境/压力/QPower 编排，不等于主谱计算。`dashboard.py` 是 GUI 兼容入口。`scripts` 存通用运行和文档/版本维护工具。子项目拥有自己的 README、代码、测试、output；主 CLI 和 GUI 使用的报告接口在主库保留兼容导出，实际 regime_pi 实现在子项目内。

[逐函数参考](code_reference.md) 列出每个函数（包含私有函数、方法及嵌套函数）的签名、源码行链接、docstring、静态调用和显式异常。子项目也有同样索引。索引反映实现，不把静态调用清单当作完整运行时调用图。阅读某个函数时沿源码链接查看分支与循环，结合本页数据流程和测试契约。

## 下载与输入验证

`cli.main → load_config → field_config → LocalJHTDB / fetch_snapshot → VelocityStore / Catalog → validate_snapshot`。

config 拒绝未知键，固定生产 dataset、周期域与完整网格。时间是 1-based stored index，物理时间 `(time_index-1)*0.002`。配置 grid/request/tile 是 xyz；NumPy 空间轴为 zyx；Giverny cutout 由 canonicalize_cutout 转为 component-first。

速度请求默认 `256×256×128`，每次 96 MiB，严格串行；checksum tile 默认 `128³`。压力服务端梯度使用独立的 PressureGradientConfig：请求 `128×128×64`，checksum tile `16³`。下载器持有 request lock，失败按配置重试/指数退避；写入后读回 checksum；catalog 保存 tile 状态。部分 request 可以重新下载但只写待完成 tile。验证检查覆盖、shape、float32、有限值、tile checksum、接缝统计，再写 input manifest 与验证状态。输入 bytes 的校验比目录名/大小可靠。

`doctor` 不是完全无副作用的纯查询：检查路径可写性，部分情况下建立目录/运行记录。`auth status` 不发科学数据请求，也不等同于 token 的网络有效性。`smoke` 才执行小型在线验证。

## 主物理计算

记 `G` 为滤波器，`ū=G*u`，`A_i=u_j ∂_j u_i`，`τ_ij=G*(u_i u_j)-ū_iū_j`。重复指标求和。

```text
W_full     = ū_i G*A_i
W_resolved = ū_i ū_j ∂_j ū_i
pi         = τ_ij ∂_j ū_i
s_bar      = ∂_j(ū_i τ_ij)
delta_w    = W_full - W_resolved = s_bar - pi
residual   = W_full - W_resolved + pi - s_bar
```

负 stored pi 是 forward cascade，正值是 backscatter；LES flux 为 `-pi`。压力功率 `q=-u·∇P` 是另一个物理量，不能当作 pi。P 为运动学压力 p/rho。

谱导数使用 `i*k` 与周期 FFT，x/y/z 导数映射到数组轴 2/1/0。Gaussian 可分离：每轴 `exp(-0.5*(sigma_grid*theta)^2)`，theta 为每格点角波数。smooth-sharp 径向传递 `0.5*erfc((|k|-kc)/(sqrt(2)*w))`，`kc=pi/(sigma_grid*dx)`、`w=alpha*kc`。生产 alpha=0.1171875。所有尺度使用相同 alpha。

`process_batch` 先验证输入与资源，建立九分量原始梯度及十二个源频谱（3 速度、3 对流加速度、6 对称乘积），顺序调用 process_full/finalize_result。memory 模式存 RAM；memmap 模式 disk_fft 在保留完整变换轴的 slab 上完成各轴 FFT，不能对每个小立方独立 FFT。滤波频谱副本不修改共享源频谱。不同 sigma 的 QA 和存储仍各自计算。

`process_full` 写 staging：滤波速度，原/滤波梯度，两个 work，六个对称 τ 贡献累加 pi 和 SGS transport，再求 s_bar，计算散度和 regime。浮点场保存 float32，统计大量使用 float64 累加。这里没有抽样减少科学格点；GUI/图片的显示采样另行记录。

## Regime：两种判据必须分清

磁盘 `regime` 由 `regime_codes_from_thresholds` 生成。定义 `eps_full=max(eps_abs,eps_rel*RMS(W_full))`，resolved 同理；只有严格 `>eps` 或 `<-eps` 才进入正/负类，其余为 0 uncertain。即使 eps=0，精确零仍 uncertain。

Cq 与 regime_pi 用 work 原值重新分类，按 `<0` 分负/非负，零在非负侧，没有 uncertain，从而六区覆盖全域。两者在同号区按 `delta_w>=0` 分 +/-。

| 编码/label | work 符号 | delta 条件 |
|---|---|---|
| 1 / 1+ | full+、resolved+ | >=0 |
| 2 / 1- | full+、resolved+ | <0 |
| 3 / 2 | full+、resolved− | 任意 |
| 4 / 3 | full−、resolved+ | 任意 |
| 5 / 4+ | full−、resolved− | >=0 |
| 6 / 4- | full−、resolved− | <0 |

block 的成对统计读磁盘 regime 编码，因此 uncertain 不归入 Q1..Q4，不能直接与 Cq 的全域分区计数对比。

Cq 五场 `pi,s_bar,work_full,work_resolved,delta_w` 分别统计 `sum_q/N`（全域归一贡献）和 `sum_q/N_q`（区内条件均值）；各区贡献相加应恢复全域均值。regime_pi 的方向 mean/fraction/intensity 分母分别为方向点数、区点数、区点数，精确 pi=0 不属正负方向。

## QA、存储与完整性

全域 divergence 检查原场与滤波场；sbar QA 检查能量残差相对 RMS 和周期净 s_bar 相对于净 pi 的比值；近零分母用报告中的状态解释，不能简单把 None 当零。weak_asymmetry 记录 signed mean、RMS、正负贡献、|pi| 分位值及极值；AbsPiPercentileAccumulator 保留所需尾部以获取分位统计。Cq 验证分区 closure。

正式提交生成字段 hash、manifest、QA 链，staging 原子移动后创建 COMPLETE。reader 要求主结果和共享梯度 COMPLETE，schema、shape 及输入 manifest hash 一致。重算报告的接口会维护报告/hash 元数据，不能手动编辑 JSON。result schema 与 report version 分开维护。

复用不仅看文件存在：参数、schema、输入来源、完成状态及报告有效性均参与检查。失败退出后保留可验证输入；临时 batch 缓存会清理或重建。锁按下载/生产/输入/strain 等职责隔离，同一结果不要并行写。

## 压力与 QPower

`pressure_local` 用 cutout 下载标量压力，按块持久化 manifest；FD4 计算 `(P[i-2]-8P[i-1]+8P[i+1]-P[i+2])/(12*h)`，读取周期两层 halo。follow 只在所有依赖压力块已经校验时计算，依赖 checksum 不匹配需重算；写锁防止双写。同一缓存恢复需保持 block-size。30 分钟无下载进展的 follow 退出，all 模式下载失败通知差分线程停止。

服务端 `--field pressure_gradient` 使用 getData fd4noint，是独立采集路径，不是 `pressure_local` 的别名。QPower preflight 检查字段/shape/来源，完整数组加载后计算 q/u² 与事件集合。绘图 stride 只用于可视化；统计全格点。初始 QPower 是全数组实现，后续 threshold/tails/ranges/angles 使用分块读，不能因此推断初始流程在 24 GB RAM 可行。

## 子项目与扩展位置

block statistics 使用未滤波速度的 SijSij；额外 strain 计算/缓存归 block 目录，主库提供兼容入口。pi_slices 只读取指定平面；scatter 分块全计数并检查 PDF 积分；pi_pdf 明确采用 LES 符号；flux_plateau 只读小报告，不扫数组。具体分箱、零值、分位和输出契约见各自 README。

修改公式需要相应解析场/守恒/closure 测试；修改 schema 要更新 config/store/reader/GUI 与数据格式文档；增加命令应更新 CLI 参考与端到端入口。先运行小域合成测试，真实全域下载/计算是昂贵的独立验证，不以单元测试通过代替。
