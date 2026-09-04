# YAHAHA 推荐系统 MVP

这是一个基于 MicroLens-50K 的可复现推荐系统工程 MVP，完整链路为：

```text
MicroLens 原始数据 -> 离线处理/训练 -> 推荐 API -> 用户行为
        -> Dashboard 指标 -> 内容运营 -> 推荐结果变化
```

## 项目简介

项目采用 CPU ItemCF、FastAPI/SQLite 和 React/Vite，提供从离线训练到线上反馈与运营的完整本地运行链路。原始数据、数据库与模型产物不会提交到 Git；验证命令和运行记录见 [测试与验证](docs/VERIFICATION.md)。

## 目录结构

```text
backend/       FastAPI、SQLite、认证、推荐服务和运营接口
frontend/      React 用户信息流、个人页、Dashboard 和内容运营界面
pipeline/      数据审计、时间切分、训练、评估和模型导出
scripts/       一键测试与构建脚本
tests/         数据、模型和 API 自动化测试
docs/          设计、数据、API、评估和验证文档
data/          本地原始/处理数据及 SQLite（Git 忽略）
models/        本地模型产物（Git 忽略）
```

## 环境要求

- Windows PowerShell（文档命令按 Windows 编写）
- Python 3.12+
- Node.js 20+
- pnpm
- 至少 2 GB 可用内存

## 1. 获取并放置数据

数据集来源为 [MicroLens 官方仓库](https://github.com/westlake-repl/MicroLens)。下载 MicroLens-50K 后，将以下三个原始文件放入 `data/raw/`；不要把数据提交到仓库：

```text
data/raw/MicroLens-50k_pairs.csv
data/raw/MicroLens-50k_titles.csv
data/raw/MicroLens-50k_likes_and_views.txt
```

本项目记录了文件 SHA-256、字段和实测统计；下载后先按 [数据处理文档](docs/DATA.md) 核对版本。

## 2. 安装依赖

在仓库根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
pnpm --dir frontend install --frozen-lockfile
```

如 PowerShell 阻止激活脚本，也可以不激活，后续把 `python` 替换为 `.\.venv\Scripts\python.exe`。

## 3. 数据处理与离线训练

```powershell
python pipeline/inspect_raw.py --output data/artifacts/raw_audit.json
python pipeline/prepare_data.py --output-dir data/processed
python pipeline/train_itemcf.py --stage validation --report data/artifacts/validation_evaluation.json
python pipeline/train_itemcf.py --stage final --report data/artifacts/final_evaluation.json
```

最终模型写入 `models/itemcf-0022f60b5e4b.json.gz`。完整 CPU 训练在开发机实测约 148.9 秒；算法、baseline、指标和 Badcase 见 [模型评估报告](docs/EVALUATION.md)。

## 4. 初始化数据库

默认值已经写在 `.env.example`，应用未额外加载 `.env` 文件时也会使用相同默认值。如需自定义，请在启动进程前设置对应环境变量。

```powershell
python -m backend.app.seed
```

该命令会导入内容和模型版本，并创建 3 个普通用户和 1 个管理员。

| 角色 | 用户名 | 密码 | MicroLens 用户映射 |
| --- | --- | --- | ---: |
| 普通用户 | `alice` | `alice123` | 1 |
| 普通用户 | `bob` | `bob12345` | 2 |
| 普通用户 | `carol` | `carol123` | 3 |
| 管理员 | `admin` | `admin123` | 无 |

以上仅为本地演示账号，密码入库后保存为带随机盐的 PBKDF2 哈希。登录页也支持注册；新账号是与数据集身份隔离的冷启动普通用户。

## 5. 启动本地 Demo

终端 1（后端）：

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000
```

终端 2（前端）：

```powershell
pnpm --dir frontend run dev
```

- Demo：`http://127.0.0.1:5173/`
- 后端健康检查：`http://127.0.0.1:8000/api/health`
- OpenAPI：`http://127.0.0.1:8000/docs`

前端通过 Vite 的 `/api` 代理访问后端，不需要额外配置跨域。

## 6. Smoke 与完整验证

```powershell
powershell -ExecutionPolicy Bypass -File scripts/verify_delivery.ps1
```

脚本会检查原始数据、处理数据和模型是否存在，运行全部 Python 测试，并用锁文件安装前端依赖后执行生产构建。也可分别执行：

```powershell
python -m unittest discover -s tests -v
pnpm --dir frontend install --frozen-lockfile
pnpm --dir frontend run build
```

## 演示顺序

1. 展示数据来源目录、`split_manifest.json` 和训练/评估命令。
2. 登录 Alice 和 Bob，对比不同个性化信息流。
3. 注册新用户，展示冷启动 fallback。
4. 播放、点赞、收藏或“不感兴趣”，展示个人画像和后续排序变化。
5. 登录管理员，切换 Dashboard 时间范围、查看趋势、热门内容、请求链路并导出 CSV。
6. 配置定向强推，再批量下线内容，验证目标信息流变化且下线内容无法通过直连接口获取。

MicroLens-50K 原始文件没有视频或封面 URL 映射，因此界面使用明确标识的确定性演示缩略图；它不会把无关图片冒充原始封面。后端和前端已保留 `cover_url` 扩展位。

## 文档索引

- [数据处理](docs/DATA.md)
- [模型评估](docs/EVALUATION.md)
- [数据库与 API](docs/API.md)
- [系统设计](docs/SYSTEM_DESIGN.md)
- [工程决策](docs/DECISIONS.md)
- [完成度与 AI 协作](docs/COMPLETION.md)
- [测试与验证](docs/VERIFICATION.md)
