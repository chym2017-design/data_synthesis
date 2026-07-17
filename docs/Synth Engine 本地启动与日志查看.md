# Synth Engine 本地启动与日志查看

本文档适用于 Windows PowerShell。项目目录为：

```text
D:\HW\synth_engine_offline\synth_engine
```

## 1. 一键启动（推荐）

直接双击项目根目录的：

```text
start.bat
```

一个命令行窗口会同时显示：

```text
[backend] 后端 API、模型测试和异常日志
[frontend] 前端编译、热更新和代理日志
[system] 启动地址、日志文件和停止状态
```

完整日志同时保存在：

```text
logs\local-年月日-时分秒.log
```

按 `Ctrl+C` 会同时停止本次脚本启动的前端和后端。脚本还会检查 3000、8080 端口，防止重复启动。

## 2. 第一次运行

打开 PowerShell，执行：

```powershell
cd D:\HW\synth_engine_offline\synth_engine
cd frontend
npm ci
cd ..
python -m synth_engine.admin create localtest
```

`npm ci` 安装前端依赖，通常只需在第一次运行或 `package-lock.json` 更新后执行。`create localtest` 会创建本地测试用户及 `localtest-xxxxxxxx` 工作空间；重复执行不会重复创建或清空数据。

## 3. 分开启动后端命令行

打开第一个 PowerShell 窗口：

```powershell
cd D:\HW\synth_engine_offline\synth_engine
$env:SYNTH_DEV_USER="localtest"
python -m uvicorn synth_engine.api.main:app --host 127.0.0.1 --port 8080 --reload --log-level info
```

这个窗口不能关闭。它显示：

- 浏览器调用了哪个 API；
- HTTP 状态码；
- LLM/Embedding 测试成功或失败；
- Python 异常和调用栈；
- 后端代码变化后的自动重载。

`SYNTH_DEV_USER` 只对本机回环地址生效，且只在当前 PowerShell 窗口有效。ECS 没有设置这个变量，生产登录仍由 Nginx 密码保护。

## 4. 分开启动前端命令行

再打开第二个 PowerShell 窗口：

```powershell
cd D:\HW\synth_engine_offline\synth_engine\frontend
npm run dev -- --host 127.0.0.1 --port 3000
```

这个窗口显示前端编译、热更新和 API 代理错误，也不能关闭。

浏览器打开：

```text
http://127.0.0.1:3000/synth/
```

本地测试不需要输入网页密码。

## 5. 如何判断 API 是否成功

后端窗口会持续打印类似日志：

```text
INFO: 127.0.0.1 - "GET /api/system/me HTTP/1.1" 200 OK
INFO: LLM 连接测试成功 model=xxx duration=1.2
WARNING: Embedding 连接测试失败 model=BAAI/bge-m3 error=Error code: 403 ...
```

常见状态码：

| 状态码 | 含义 |
| --- | --- |
| `200` | API 请求成功 |
| `400` | 参数或模型配置有问题；查看同一窗口前面的具体错误 |
| `401/403` | 用户认证、API Key、模型权限或账户余额问题 |
| `404` | 请求地址、运行 ID、文件或模型接口不存在 |
| `422` | 参数超出限制或字段格式错误，例如数量超过 20 |
| `500` | 后端代码异常；查看随后打印的 Python 调用栈 |

按 `F12` 打开浏览器开发者工具，在“网络/Network”页也能查看每个 `/api/...` 请求的状态码和返回内容。

## 6. 实时查看 LLM 调用记录

合成任务启动后，可以在第三个 PowerShell 窗口找到最新日志：

```powershell
cd D:\HW\synth_engine_offline\synth_engine
$log = Get-ChildItem .\workspaces\localtest-*\runs\outputs\*\llm_log.jsonl | Sort-Object LastWriteTime -Descending | Select-Object -First 1
$log.FullName
Get-Content -LiteralPath $log.FullName -Tail 30 -Wait
```

`-Wait` 会持续等待新日志。按 `Ctrl+C` 退出实时查看。

如果提示找不到 `llm_log.jsonl`，说明还没有启动过合成任务，或者任务尚未创建模型调用日志。

## 7. 停止本地网站

分别切换到后端和前端 PowerShell 窗口，各按一次：

```text
Ctrl+C
```

确认两个窗口都回到 PowerShell 提示符后，本地网站即停止。不要直接结束未知的 Python 或 Node 进程，以免误伤其他本地项目。

## 8. 常见启动问题

### 端口已经被占用

```powershell
Get-NetTCPConnection -LocalPort 3000,8080 -State Listen | Select-Object LocalPort,OwningProcess
```

通常表示旧的本地前端或后端仍在运行。回到对应窗口按 `Ctrl+C`，不要同时启动两套服务。

### 前端能打开但一直显示“读取中”

检查后端窗口是否运行，以及是否执行了：

```powershell
$env:SYNTH_DEV_USER="localtest"
```

### Embedding 返回 403 / code 30001

当前 SiliconFlow 返回的是账户余额不足。需要充值或更换有余额且有 `BAAI/bge-m3` 权限的 API Key，不是本地端口或页面故障。
