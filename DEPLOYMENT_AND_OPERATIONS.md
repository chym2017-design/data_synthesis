# Synth Engine 部署与运维手册

本文档适用于当前 Synth Engine ECS 部署，供后续版本更新、日常运维、备份恢复和密码修改使用。

## 1. 当前环境

| 项目 | 当前值 |
| --- | --- |
| 服务器公网 IP | `101.245.66.42` |
| 操作系统 | CentOS 7.9 |
| 访问地址 | `http://101.245.66.42/synth/` |
| 网页认证用户名 | `synthadmin` |
| 应用容器 | `synth-engine` |
| 应用服务 | `synth-engine.service` |
| 反向代理 | Nginx |
| 应用内部端口 | `127.0.0.1:8080` |
| 公网端口 | `80` |

网页密码不要写入本文档、Git 仓库、脚本或命令历史。网页认证密码和 ECS 的 root 密码是两套完全独立的密码。

## 2. 部署架构

```text
浏览器
  │ http://101.245.66.42/synth/
  ▼
Nginx :80
  │ Basic Auth 访问认证
  ▼
127.0.0.1:8080
  ▼
Docker 容器 synth-engine
  ▼
FastAPI + Vue 前端
```

服务器上原有的 `mcp-server` 容器使用公网 `8000` 端口，与本项目相互独立，不要误删或停止。

## 3. 重要文件位置

### 3.1 ECS 宿主机

| 内容 | 路径 |
| --- | --- |
| 项目根目录 | `/opt/synth_engine` |
| Python 后端 | `/opt/synth_engine/synth_engine` |
| 前端构建产物 | `/opt/synth_engine/frontend/dist` |
| 模型与嵌入配置 | `/opt/synth_engine/configs` |
| 模板 | `/opt/synth_engine/synth_engine/templates` |
| 合成输出 | `/opt/synth_engine/runs/outputs` |
| 质检输出 | `/opt/synth_engine/runs/qc_results` |
| Dockerfile | `/opt/synth_engine/Dockerfile` |
| Nginx 配置 | `/etc/nginx/conf.d/aiserver.fun.conf` |
| 网页密码文件 | `/etc/nginx/.htpasswd-aiserver` |
| systemd 服务 | `/etc/systemd/system/synth-engine.service` |
| HTTPS 证书（保留） | `/etc/letsencrypt/live/aiserver.fun` |

Nginx 配置文件名 `aiserver.fun.conf` 是历史命名；它目前也负责 IP 地址访问。

### 3.2 Docker 容器

容器内项目路径为 `/app`。以下目录通过宿主机挂载，重建容器后不会丢失：

```text
/opt/synth_engine/configs                    -> /app/configs
/opt/synth_engine/runs                       -> /app/runs
/opt/synth_engine/synth_engine/templates     -> /app/synth_engine/templates
```

因此，更新时必须重点保护 `configs`、`runs` 和 `templates`。

## 4. 日常检查

### 4.1 检查服务状态

```bash
systemctl status docker --no-pager
systemctl status synth-engine --no-pager
systemctl status nginx --no-pager
docker ps
```

三个服务正常时应显示 `active (running)`，容器列表中应同时存在 `synth-engine` 和原有的 `mcp-server`。

### 4.2 检查应用健康状态

应用内部健康检查不经过网页密码：

```bash
curl http://127.0.0.1:8080/api/health
```

正常返回：

```json
{"status":"ok","version":"0.1.0"}
```

公网检查会提示输入网页密码：

```bash
curl -u synthadmin http://101.245.66.42/api/health
```

### 4.3 检查监听端口

```bash
ss -lntp
```

当前应包含：

- `80`：Nginx 公网入口；
- `127.0.0.1:8080`：Synth Engine，仅服务器本机可访问；
- `8000`：原有 `mcp-server`；
- `22`：SSH。

## 5. 服务启停与重启

```bash
# 重启应用
systemctl restart synth-engine

# 停止/启动应用
systemctl stop synth-engine
systemctl start synth-engine

# 修改 Nginx 配置后检查并重新加载
nginx -t && systemctl reload nginx

# 查看是否开机自启
systemctl is-enabled synth-engine
systemctl is-enabled nginx
```

一般不要直接执行 `docker run` 启动 Synth Engine，应通过 `systemctl` 管理，否则可能产生重名容器或失去开机自启能力。

## 6. 更新网站版本

仅替换 `/opt/synth_engine` 中的文件不会更新正在运行的后端和前端，因为当前容器使用的是构建时复制进去的代码。上传新文件后，必须重新构建镜像并重启服务。

### 6.1 更新前备份

登录 ECS 后执行：

```bash
mkdir -p /opt/backups
tar -czf /opt/backups/synth-engine-data-$(date +%Y%m%d-%H%M%S).tar.gz \
  /opt/synth_engine/configs \
  /opt/synth_engine/runs \
  /opt/synth_engine/synth_engine/templates \
  /etc/nginx/conf.d/aiserver.fun.conf \
  /etc/nginx/.htpasswd-aiserver \
  /etc/systemd/system/synth-engine.service
```

备份文件包含 API 密钥和网页密码哈希，权限应限制为 root：

```bash
chmod 600 /opt/backups/synth-engine-data-*.tar.gz
```

### 6.2 从本机打包代码

在 Windows PowerShell 中进入项目根目录，打包时排除运行数据、模型配置、用户模板和测试文件：

```powershell
tar -czf synth-engine-update.tar.gz `
  --exclude=.git `
  --exclude=wheels `
  --exclude=runs `
  --exclude=configs `
  --exclude=synth_engine/templates `
  --exclude='test_*.py' `
  Dockerfile .dockerignore requirements.txt synth_engine frontend deploy
```

上传到服务器：

```powershell
scp synth-engine-update.tar.gz root@101.245.66.42:/tmp/
```

如果使用专用私钥：

```powershell
scp -i "$HOME/.ssh/codex_aiserver_ed25519" synth-engine-update.tar.gz root@101.245.66.42:/tmp/
```

### 6.3 在 ECS 上发布

```bash
cd /opt/synth_engine

# 给当前镜像添加回滚标签
docker tag synth-engine:latest synth-engine:rollback-$(date +%Y%m%d-%H%M%S)

# 覆盖代码；被排除的持久化目录不会受影响
tar -xzf /tmp/synth-engine-update.tar.gz -C /opt/synth_engine

# 构建新镜像
DOCKER_BUILDKIT=1 docker build --network host -t synth-engine:latest .

# 重启并验证
systemctl restart synth-engine
curl http://127.0.0.1:8080/api/health
systemctl status synth-engine --no-pager
```

构建期间旧容器仍然运行，通常只在 `systemctl restart synth-engine` 时中断几秒。

### 6.4 `/synth/` 前缀要求

当前入口使用 `/synth/`。前端必须满足以下任一条件：

1. Vite 构建配置使用 `base: '/synth/'`；或
2. `frontend/dist/index.html` 的 `<head>` 中保留：

```html
<base href="/synth/" />
```

替换整个 `frontend/dist` 后如果遗漏该配置，页面可能打开但菜单路由无法使用。

### 6.5 发布后验收

```bash
curl http://127.0.0.1:8080/api/health
curl -u synthadmin -I http://101.245.66.42/synth/
docker logs --tail 100 synth-engine
```

随后用浏览器检查：

- `http://101.245.66.42/synth/` 能否登录；
- 菜单切换是否正常；
- 配置是否仍存在；
- 历史结果是否仍可查看；
- 创建一个小规模测试任务是否成功。

## 7. 版本回滚

查看可用镜像：

```bash
docker images | grep synth-engine
```

选择更新前的回滚标签，例如 `synth-engine:rollback-20260715-170000`：

```bash
docker tag synth-engine:rollback-20260715-170000 synth-engine:latest
systemctl restart synth-engine
curl http://127.0.0.1:8080/api/health
```

镜像回滚只回滚程序代码，不会回滚 `configs`、`runs` 和 `templates`。如果这些数据也被错误修改，需要从 `/opt/backups` 中单独恢复。

不要使用 `docker system prune -a`，否则可能删除回滚镜像以及原有 `mcp-server` 相关镜像。

## 8. 修改网页访问密码

网页认证文件：

```text
/etc/nginx/.htpasswd-aiserver
```

文件中保存用户名和密码哈希，不保存明文密码。

### 8.1 修改 `synthadmin` 密码

```bash
htpasswd /etc/nginx/.htpasswd-aiserver synthadmin
chown root:nginx /etc/nginx/.htpasswd-aiserver
chmod 640 /etc/nginx/.htpasswd-aiserver
nginx -t && systemctl reload nginx
```

`htpasswd` 会要求输入两次新密码。输入时终端不会显示字符，这是正常现象。

### 8.2 修改网页用户名

先添加新用户，确认成功后再删除旧用户。以下示例将用户名改为 `admin`：

```bash
htpasswd /etc/nginx/.htpasswd-aiserver admin
htpasswd -D /etc/nginx/.htpasswd-aiserver synthadmin
chown root:nginx /etc/nginx/.htpasswd-aiserver
chmod 640 /etc/nginx/.htpasswd-aiserver
nginx -t && systemctl reload nginx
```

不要使用带明文密码的 `htpasswd -b` 命令，否则密码会进入终端历史和进程参数。

## 9. ECS root 密码与 SSH 密钥

### 9.1 修改 root 密码

已经登录服务器时执行：

```bash
passwd root
```

root 密码只用于 ECS/SSH，不是网页密码。

### 9.2 忘记 root 密码

如果密码和 SSH 密钥都无法登录：

1. 登录华为云 ECS 控制台；
2. 找到公网 IP 为 `101.245.66.42` 的服务器；
3. 选择“更多 → 密码/密钥 → 重置密码”；
4. 设置新密码；
5. 按控制台提示重启服务器；
6. 使用 `ssh root@101.245.66.42` 登录；
7. 登录后检查 Docker、Nginx 和 Synth Engine 服务。

重启后执行：

```bash
systemctl status docker --no-pager
systemctl status synth-engine --no-pager
systemctl status nginx --no-pager
```

### 9.3 管理 SSH 公钥

公钥文件位置：

```text
/root/.ssh/authorized_keys
```

该文件曾设置不可变和仅追加属性。修改前检查：

```bash
lsattr /root/.ssh/authorized_keys
```

如显示 `i` 或 `a`，先解除属性：

```bash
chattr -ia /root/.ssh/authorized_keys
```

编辑或追加公钥后恢复权限：

```bash
chown root:root /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
chattr +ia /root/.ssh/authorized_keys
```

至少保留一种已经实际验证可登录的方式，再关闭当前 SSH 会话。不要在未验证新密钥时删除旧密钥或禁用密码登录。

## 10. 日志与故障排查

### 10.1 应用日志

```bash
journalctl -u synth-engine -n 200 --no-pager
journalctl -u synth-engine -f
docker logs --tail 200 synth-engine
docker logs -f synth-engine
```

### 10.2 Nginx 日志

```bash
tail -n 200 /var/log/nginx/access.log
tail -n 200 /var/log/nginx/error.log
```

### 10.3 SSH 登录日志

```bash
tail -n 200 /var/log/secure
```

### 10.4 常见问题

#### 浏览器返回 502

先检查应用：

```bash
systemctl status synth-engine --no-pager
docker logs --tail 200 synth-engine
curl http://127.0.0.1:8080/api/health
```

如果应用未运行：

```bash
systemctl restart synth-engine
```

#### 浏览器反复要求输入密码

检查网页密码文件权限和 Nginx 日志：

```bash
chown root:nginx /etc/nginx/.htpasswd-aiserver
chmod 640 /etc/nginx/.htpasswd-aiserver
nginx -t && systemctl reload nginx
tail -n 100 /var/log/nginx/error.log
```

#### `/synth/` 页面空白或菜单打不开

检查首页是否包含基础路径：

```bash
grep '<base href="/synth/"' /opt/synth_engine/frontend/dist/index.html
```

若刚替换了前端，需要修复基础路径、重建镜像并重启。

#### 更新后配置或历史结果消失

检查挂载目录是否存在：

```bash
ls -la /opt/synth_engine/configs
ls -la /opt/synth_engine/runs
ls -la /opt/synth_engine/synth_engine/templates
systemctl cat synth-engine
```

不要在空目录状态下反复启动容器，以免误以为数据已被镜像恢复。

#### SSH 密码和密钥都被拒绝

如果仍有已经登录的终端，先检查：

```bash
passwd -S root
sshd -T | grep -E 'passwordauthentication|permitrootlogin|pubkeyauthentication'
ls -ld /root /root/.ssh
ls -l /root/.ssh/authorized_keys
lsattr /root/.ssh/authorized_keys
tail -n 100 /var/log/secure
```

如果没有任何可用会话，通过华为云控制台重置 root 密码。

## 11. 数据备份与恢复

### 11.1 手工备份

```bash
mkdir -p /opt/backups
tar -czf /opt/backups/synth-engine-persistent-$(date +%Y%m%d-%H%M%S).tar.gz \
  /opt/synth_engine/configs \
  /opt/synth_engine/runs \
  /opt/synth_engine/synth_engine/templates
chmod 600 /opt/backups/synth-engine-persistent-*.tar.gz
```

建议定期把备份下载到另一台机器，不能只保存在同一块 ECS 系统盘中。

### 11.2 恢复前注意事项

恢复会覆盖当前配置和数据。先停止应用并再次备份当前状态：

```bash
systemctl stop synth-engine
tar -czf /opt/backups/before-restore-$(date +%Y%m%d-%H%M%S).tar.gz \
  /opt/synth_engine/configs \
  /opt/synth_engine/runs \
  /opt/synth_engine/synth_engine/templates
```

确认备份文件后再解压目标备份，最后启动并检查：

```bash
tar -xzf /opt/backups/目标备份文件.tar.gz -C /
systemctl start synth-engine
curl http://127.0.0.1:8080/api/health
```

## 12. 合成数量与并发说明

- “合成数量”是基础样本数量，不一定等于最终导出行数；
- 系统至少会生成一个单轮基础样本；
- 单轮模型响应可能包含多条以“用户：”开头的内容；
- 后端会将这些内容拆成多条独立数据，因此最终行数可能超过填写值；
- “并发”只是同时执行的模型请求数，不会直接决定最终数据数量。

如果业务要求“填写多少就严格输出多少”，需要修改流水线，在单轮拆分后对最终结果进行严格限量。

## 13. 安全注意事项

1. 当前使用 HTTP IP 访问，网页认证和业务内容没有 HTTPS 加密，不要在不可信网络中使用。
2. 不要把 `configs/*.yaml`、网页密码、root 密码或私钥提交到公开 Git 仓库。
3. 修改 SSH 配置前保持一个已登录终端，修改后先执行 `sshd -t`。
4. 不要直接开放 `8080` 到公网。
5. 不要删除或停止不属于本项目的 `mcp-server` 容器。
6. 定期更新 API 密钥、网页密码和 root 密码。
7. 重要更新前同时保留代码镜像回滚点和持久化数据备份。

