# Hub 验证清单

- [x] GUI ping / get_config / set_config / get_status — `test_app_host_host.c`, `test_protocol.py`
- [x] FC 强制使能 — `test_protocol.py::test_validate_force_fc_on`
- [x] 锁开启拒绝 set_config — `test_app_host_host.c::test_locked`
- [x] FC 帧到达所有已使能口；不到未使能口 — `test_router_logic.py::test_fc_to_enabled_only`
- [x] 支路帧只到 FC — `test_router_logic.py::test_branch_only_to_fc`
- [x] 两支路互不串话 — `test_router_logic.py` routing model (branch → FC only)
- [ ] 单口 fault silent 后其余口仍通
- [ ] 1 Mbps 双节点 ACK 稳定（每口抽测）
- [ ] 9V / 36V 供电边界（硬件就绪后）
- [ ] ArduPilot + 12 ESC 联调（硬件就绪后）
