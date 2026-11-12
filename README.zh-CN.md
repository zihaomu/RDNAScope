# RDNAScope

RDNAScope是一层薄的RDNA观测工具。使用项目提供启动命令、运行环境、GPU资源和可选scope标记；工具负责有界调用官方ROCm采集／导出、只读核对原生证据、生成小型scope/rank摘要，并打开官方Perfetto UI。

模型输出oracle、关闭trace的正式测速、候选修改及采用决策由使用项目维护。RDNAScope不内置应用adapter目录。

当前本地源码为**0.3.0a1薄工具alpha**。一个锁定ROCm环境下的R9700合成eager、Graph和双rank采集已通过限定资格；监控开销及模型性能仍未资格化。实际范围见[支持矩阵](docs/thin-support.md)，实施收束见[主计划](docs/rdnascope_thin_tool_master_plan_20261112.md)。

```bash
rdnascope --config .rdnascope.toml doctor
rdnascope --config .rdnascope.toml record --output ./traces/run-001 -- ./run_workload.sh
rdnascope --config .rdnascope.toml query ./traces/run-001 --view coverage
rdnascope --config .rdnascope.toml report ./traces/run-001
rdnascope --config .rdnascope.toml view ./traces/run-001 --port 9002 --idle-seconds 300
```

将[通用配置](profiles/machine.example.toml)复制到使用项目并填写官方工具路径。只有`record`启动应用；查询和报告离线执行。原始rocpd DB及PFTrace保存在使用项目显式选择的run目录中，工具保留SHA和失败记录，不制造另一套trace格式。

配置、Graph/rank限制及VS Code转发见[使用指南](docs/thin-user-guide.md)；旧宽alpha的兼容边界见[迁移说明](docs/thin-migration.md)。许可证为Apache-2.0。
