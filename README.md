# Synth Engine 数据合成引擎

Synth Engine 是一个面向意图识别数据的配置、合成和质检平台。当前版本提供多用户工作空间隔离、统一任务队列、模型连接测试和 Web 管理界面。

## 当前功能

页面按照实际业务流程排列：

```text
使用指南
  → 模板配置
  → 合成前质检
  → 数据合成
  → 合成后质检
  → 任务队列
  → 结果查看
  → 配置管理
```

- 管理员在 ECS 后台创建网页账号，用户不能自行注册或修改密码；
- 每个用户自动获得 `用户名-8位短标识` 格式的独立工作空间；
- 模型配置、模板、上传资源、合成结果和质检结果按用户隔离；
- 合成与质检共用全局任务队列，默认最多同时运行 5 个任务；
- 每次合成和质检的处理上限由统一系统配置控制；
- LLM 和 Embedding 配置支持页面连接测试；
- 所有账号都可以查看全局运行/排队任务及排队位置；
- 三类任务统一使用 `用户名_任务类型_YYMMDDHHMMSS_UUID` 作为任务 ID 和输出目录名；
- 保留浏览器 Basic Auth 登录，并提供“退出登录”按钮。

任务条数、模型并行度和全局任务并发数统一配置在
`configs/system_limits.yaml`。修改后重启服务，后端校验和前端界面会同时使用新值。

## 本地一键启动

Windows 下双击：

```text
start.bat
```

脚本会同时启动：

- 后端：`http://127.0.0.1:8080`
- 前端：[http://127.0.0.1:3000/synth/](http://127.0.0.1:3000/synth/)

前后端日志会在同一个窗口中分别以 `[backend]`、`[frontend]` 开头，并保存到 `logs/local-时间.log`。按 `Ctrl+C`，再按提示输入 `Y`，即可同时停止。

首次运行若缺少依赖，脚本会尝试安装。也可以手工执行：

```powershell
python -m pip install -r requirements.txt
cd frontend
npm ci
```

完整本地说明见 [Synth Engine 本地启动与日志查看.md](docs/Synth%20Engine%20本地启动与日志查看.md)。

## ECS 访问与部署

当前部署入口：

[http://101.245.66.42/synth/](http://101.245.66.42/synth/)

生产结构：

```text
浏览器
  → Nginx :80 / Basic Auth
  → 127.0.0.1:8080
  → Docker 容器 synth-engine
  → FastAPI + Vue
  → 用户数据库和独立工作空间
```

生产环境使用 systemd 管理：

```bash
systemctl status synth-engine --no-pager
systemctl restart synth-engine
docker logs --tail 200 synth-engine
```

详细发布、备份、回滚和故障排查见 [网页部署及用户管理.md](docs/网页部署及用户管理.md)。

## 用户管理

生产服务器使用 `synth-user`：

```bash
synth-user create USER
synth-user passwd USER
synth-user disable USER
synth-user enable USER
synth-user list
```

网页密码只以 bcrypt 哈希保存在 Nginx 密码文件中。Synth Engine 的 SQLite 数据库只保存用户名、工作空间名称和启用状态，不保存密码。

## 目录结构

```text
synth_engine/
├── synth_engine/                  # Python 后端、合成流水线和质检逻辑
│   ├── api/                       # FastAPI 入口与路由
│   ├── core/                      # 配置、画像、流水线和数据模型
│   ├── llm/                       # LLM 与 Embedding 客户端
│   ├── qc/                        # 合成前/后质检
│   ├── templates/                 # 默认领域模板及 Python 实现
│   ├── tenant.py                  # 用户与工作空间映射
│   └── task_queue.py              # 单进程全局任务队列
├── frontend/                      # Vue 3 前端源码和构建产物
├── configs/                       # 默认模型配置和系统级任务限制
├── runs/                          # 旧共享结果/默认兼容目录
├── data/                          # 本地用户数据库（不提交）
├── workspaces/                    # 本地用户工作空间（不提交）
├── deploy/                        # Nginx、systemd 和用户管理脚本
├── docs/                          # 使用、原理、测试和部署文档
├── tests/                         # 多用户、队列和接口回归测试
├── synth_engine_源码参考/         # 只读参考源码，不参与构建
├── Dockerfile
├── .dockerignore
├── start.bat
└── start_local.ps1
```

生产服务器的用户目录格式：

```text
/opt/synth_engine/workspaces/<用户名-8位短标识>/
├── configs/
├── templates/
├── resources/
└── runs/
    ├── outputs/
    └── qc_results/
```

## 开发验证

后端测试：

```powershell
python -m pytest tests\test_multi_tenant.py -q
```

前端生产构建：

```powershell
cd frontend
npm ci
npm run build
```

Python 语法检查：

```powershell
python -m compileall synth_engine
```

## 重要限制

- 当前任务队列保存在单个应用进程内，服务重启后排队任务不会恢复；
- 不要直接增加多个 Uvicorn worker，否则每个进程都会产生独立队列；
- 当前公网入口为 HTTP，正式多用户使用前建议配置 HTTPS 或可信 VPN；
- `configs`、`data`、`workspaces` 和备份文件可能包含 API Key 或业务数据，不应提交到公开仓库；
- 默认 SiliconFlow Embedding 配置若返回 `403 / code 30001`，表示账号余额或调用资格不足，与本地页面无关。

## 文档索引

- [使用指南技术细节版.md](docs/使用指南技术细节版.md)：页面操作、参数含义和内部原理；
- [数据合成工作流细节.md](docs/数据合成工作流细节.md)：合成与质检流水线设计；
- [Synth Engine 本地启动与日志查看.md](docs/Synth%20Engine%20本地启动与日志查看.md)：本地启动、日志和常见问题；
- [网页部署及用户管理.md](docs/网页部署及用户管理.md)：ECS 部署、账号、备份、回滚和安全运维。
