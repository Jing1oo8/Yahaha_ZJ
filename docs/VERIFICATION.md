# 测试与验证证据

## 自动化范围

Python 测试覆盖：

- 数据时间边界、同毫秒事件不跨分区、已知实体评估集和可复现 manifest；
- ItemCF 已看过滤、候选排序、baseline 和模型序列化/加载；
- 两用户个性化差异、注册冷启动、事件幂等和曝光归属；
- request/exposure/event 链路、画像变化、管理员权限；
- 强推、批量上下线、直连接口下线过滤、恢复；
- Dashboard、用户调试和运营规则。

前端验证使用 `pnpm-lock.yaml` 锁定解析结果，并执行 Vite 生产构建。

## 一键命令

在仓库根目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_delivery.ps1
```

脚本先检查 3 个原始文件、关键处理产物和最终模型，再依次执行：

```powershell
python -m unittest discover -s tests -v
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend run build
```

任何一步失败都会返回非零退出码，不会把部分成功误报为完整通过。

## 洁净依赖环境复现方法

下列流程不复用项目虚拟环境，可用于复核 Python 依赖声明：

```powershell
python -m venv .verify-venv
.\.verify-venv\Scripts\python.exe -m pip install -r requirements.txt
.\.verify-venv\Scripts\python.exe -m unittest discover -s tests -v
```

前端使用：

```powershell
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend run build
```

原始数据和模型按题目要求不进入 Git，因此“洁净机器复现”仍需要复现者先从题目来源下载 3 个原始文件，再运行 README 中的数据处理和训练命令。这是合规前置条件，不是仓库缺失。

## 已记录结果

- 原始数据审计和完整时间切分成功。
- validation 与 final ItemCF 评估成功；最终耗时 148.9 秒。
- 2026-09-04 在全新临时 Python venv 中从 `requirements.txt` 安装成功，11 项自动化测试全部通过。
- `pnpm install --frozen-lockfile` 和 Vite 生产构建通过（1,817 个模块，产物约 226.12 kB JS、19.83 kB CSS）。
- 浏览器人工检查已覆盖桌面/移动布局、用户注册、Alice 信息流/反馈/个人页、管理员 Dashboard、用户调试、强推和内容上下线。

运行时健康检查命令：

```powershell
Invoke-RestMethod -NoProxy -Uri 'http://127.0.0.1:8000/api/health'
```
