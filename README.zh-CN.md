# RDNAScope

面向 AMD RDNA 的模型、kernel 与多卡性能诊断工具。

**0.2.0a1为证据诊断与有界优化实验的alpha版本。** 已实现独立离线核心、只读查询、能力矩阵、测速合同/参照、三类finding、类型化候选门，以及缓存与进程生命周期。R3–R6软件接口已接通；新的FreeToken GPU验收和第二卡对实测受资源占用阻塞，不能把软件完成写成硬件资格或模型提速。

```bash
python -m pip install .
rdnascope --data-dir /tmp/rdnascope-demo doctor
rdnascope --data-dir /tmp/rdnascope-demo register --run demo --identity examples/offline-identity.json examples/chrome.json
rdnascope --data-dir /tmp/rdnascope-demo query demo --view summary
rdnascope --data-dir /tmp/rdnascope-demo query demo --view kernels --limit 10
rdnascope --data-dir /tmp/rdnascope-demo analyze demo --output demo-analysis
rdnascope --data-dir /tmp/rdnascope-demo kb verify demo-analysis
rdnascope --data-dir /tmp/rdnascope-demo storage-stats
```

示例为自行构造的小型输入，不含真实模型或用户数据。注册只保存引用与SHA；同一查询重复执行复用缓存，源文件变化后拒绝查询/缓存复用。大文件不复制进仓库。必须保留源文件才能继续核验。

rocpd直接只读查询；PFTrace使用用户明确配置的官方Trace Processor，不自动下载；HTTP记录的first-text不冒充TTFT，chunk间隔不冒充ITL。未知关联、Graph覆盖、时钟和模型性能均保持未资格。

旧工程保留原路径及功能。新安装的`tlp`是显式配置的转发入口，原参数与退出码保持；不会隐式改写旧命令语义。见[迁移说明](docs/migration.md)。

R2加入可配置容量/磁盘预留、lease与引用保护、TTL/LRU预览和显式GC、ABI namespace、受限worker和官方RPC服务管理。外部证据与未登记旧缓存不进入GC，默认不自动回收；本机容量/TTL仍需owner配置。现有UI不会被接管。详见[生命周期指南](docs/lifecycle.md)和[实际验收](docs/validation-r2.md)。

编译缓存当前只验证namespace/复用协议，未运行Torch/Triton编译资格；预算属于应用层预检与监测，不是文件系统硬配额。受管生命周期目前验证于Linux。

当前支持“薄记录 → 假设 → 隔离候选 → 按类型验证 → 关闭profiler的A/A及对照 → 归档”。独立boot漂移、错误输出、条件不匹配或资源资格不足会阻止采用。模型、kernel、多卡报告共用不可变证据；缺shape不输出roofline，缺时钟资格不量化rank等待。正式采用仍是单独动作，工具不会自动改写已接受基线。

原始rocpd/官方PFTrace保持官方格式。`ui locate`生成finding对应的官方SQL，`service start`提供官方UI及VS Code端口转发说明，无自研前端。第二adapter为可实际启动的CPU数值fixture，仅验证工作流泛化；GPU兼容入口必须绑定私有环境和资源守卫，当前尚未完成新实测。

[使用流程](docs/workflows.md) · [支持矩阵](docs/support.md) · [配置](docs/configuration.md) · [契约](docs/architecture.md) · [本轮验收](docs/validation-r3r6.md) · [实施记录](docs/implementation.md) · [长期计划](docs/roadmap.md)

Agent离线工作流见[仓库skill](skills/rdnascope/SKILL.md)。开发验证：`python -m pip install -e '.[test]'`后执行`python -m pytest -q`；CI同时验证wheel在源码目录外安装运行。

项目许可证为[Apache-2.0](LICENSE)。
