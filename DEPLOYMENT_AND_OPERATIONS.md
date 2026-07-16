# Synth Engine 部署与运维手册

本文档适用于当前 Synth Engine ECS 部署，供后续版本更新、日常运维、备份恢复和密码修改使用。

## 1. 当前环境

| 项目 | 当前值 |
| --- | --- |
| 服务器公网 IP | `101.245.66.42` |
| 操作系统 | Ubuntu Server 24.04.4 LTS 64bit |
| 访问地址 | `http://101.245.66.42/synth/` |
| 网页认证用户名 | `synthadmin` |
| 应用容器 | `synth-engine` |
| 应用服务 | `synth-engine.service` |
| 反向代理 | Nginx |
| 应用内部端口 | `127.0.0.1:8080` |
| 公网端口 | `80`（安全组中的 `22` 仅允许管理员当前公网 IP） |

网页密码不要写入本文档、Git 仓库、脚本或命令历史。当前系统涉及三类彼此独立的凭据：

| 凭据 | 用在哪里 | 修改后影响什么 |
| --- | --- | --- |
| 网页账号 `synthadmin` 与网页密码 | 浏览器打开 `/synth/` 时的 Basic Auth | 只影响网页入口，不影响 SSH 和模型调用 |
| ECS 的 root/SSH 密码或 SSH 私钥 | 登录 Ubuntu 服务器 | 只影响服务器运维，不会修改网页密码 |
| LLM/Embedding API Key | Synth Engine 调用模型接口 | 只影响合成和质检，不会修改网页或 SSH 登录 |

部署时生成的随机网页初始密码只临时保存在 `/root/synth-initial-credentials.txt`。管理员保存密码后应删除该明文文件。网页密码的长期存储文件 `/etc/nginx/.htpasswd-aiserver` 中只有密码哈希，不能从中还原明文密码。

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

当前新系统只部署了 `synth-engine` 容器，没有部署旧系统中的 `mcp-server`。Synth Engine 不使用公网 `8000` 端口。

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
| Nginx 配置 | `/etc/nginx/conf.d/synth-engine.conf` |
| 网页密码文件 | `/etc/nginx/.htpasswd-aiserver` |
| 初始网页凭据（使用后删除） | `/root/synth-initial-credentials.txt` |
| systemd 服务 | `/etc/systemd/system/synth-engine.service` |

当前没有使用域名或 HTTPS 证书，入口是 IP 地址上的 HTTP。Basic Auth 只能控制访问，不能加密传输内容。

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

三个服务正常时应显示 `active (running)`，`docker ps` 中应存在一个名为 `synth-engine` 的容器。

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

`-u synthadmin` 表示使用网页账号 `synthadmin`。命令随后会提示输入网页密码，输入时密码不会显示在屏幕上。不要把密码直接写成 `-u synthadmin:明文密码`，否则可能被终端历史或进程列表记录。

### 4.3 检查监听端口

```bash
ss -lntp
```

当前应包含：

- `80`：Nginx 公网入口；
- `127.0.0.1:8080`：Synth Engine，仅服务器本机可访问；
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
  /etc/nginx/conf.d/synth-engine.conf \
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
docker build --network host -t synth-engine:latest .

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

不要使用 `docker system prune -a`，否则可能删除 Synth Engine 的回滚镜像和构建缓存。

## 8. 网页用户名与密码

浏览器打开 `http://101.245.66.42/synth/` 时出现的登录框由 Nginx Basic Auth 提供。它不是 Synth Engine 数据库账号，也不是 ECS 的 root 账号。

Nginx 从下面的文件核对用户名和密码：

```text
/etc/nginx/.htpasswd-aiserver
```

文件中每一行对应一个网页用户，格式类似 `用户名:密码哈希`。密码哈希用于验证输入是否正确，不能直接还原成明文密码。

### 8.1 查看部署时生成的初始账号

只有首次部署并且尚未删除临时文件时，才能执行：

```bash
cat /root/synth-initial-credentials.txt
```

`cat` 的作用是把文件内容显示到终端。该文件包含一次性的明文初始密码，所以只能在自己的华为云控制台中查看，不要截图、复制到群聊或提交到 Git。确认已经把密码保存到密码管理器后，删除临时文件：

```bash
rm -f /root/synth-initial-credentials.txt
```

`rm -f` 表示删除指定文件。它不会删除 Nginx 密码哈希，因此删除后网页账号仍能正常登录，只是服务器不再保留可直接查看的明文密码。

### 8.2 修改现有用户 `synthadmin` 的网页密码

第一步，交互式设置新密码：

```bash
htpasswd /etc/nginx/.htpasswd-aiserver synthadmin
```

这条命令的含义是：在密码文件中找到 `synthadmin`，用新密码哈希替换旧哈希。终端会要求输入两次新密码；输入过程中屏幕不显示字符，这是 Linux 的正常安全设计。

第二步，恢复 Ubuntu Nginx 所需的文件所有者和权限：

```bash
chown root:www-data /etc/nginx/.htpasswd-aiserver
chmod 640 /etc/nginx/.htpasswd-aiserver
```

- `chown root:www-data`：文件由 root 管理，同时允许 Ubuntu 的 Nginx 用户组 `www-data` 读取；
- `chmod 640`：root 可以读写，`www-data` 只能读取，其他用户不能访问。

第三步，检查配置并平滑重新加载：

```bash
nginx -t && systemctl reload nginx
```

- `nginx -t`：先检查 Nginx 配置语法；
- `&&`：只有前一个命令成功时才执行后一个命令；
- `systemctl reload nginx`：不停止网站，重新读取配置和密码文件。

修改完成后，用浏览器无痕窗口重新登录验证。原密码会立即失效。

### 8.3 修改网页用户名

不要先删除旧用户。正确顺序是“添加新用户 → 验证新用户 → 删除旧用户”。以下示例把用户名从 `synthadmin` 改为 `admin`。

第一步，添加新用户并设置密码：

```bash
htpasswd /etc/nginx/.htpasswd-aiserver admin
chown root:www-data /etc/nginx/.htpasswd-aiserver
chmod 640 /etc/nginx/.htpasswd-aiserver
```

此时 `synthadmin` 和 `admin` 都可以登录。先在浏览器无痕窗口中确认 `admin` 能成功登录，然后再删除旧用户：

```bash
htpasswd -D /etc/nginx/.htpasswd-aiserver synthadmin
nginx -t && systemctl reload nginx
```

`htpasswd -D` 中的 `-D` 表示只删除指定用户名。它不会删除整个密码文件。

不要使用 `htpasswd -b`。`-b` 会要求把明文密码直接写进命令，密码可能进入终端历史和进程参数。

## 9. ECS root 密码与 SSH 密钥

### 9.1 修改 root 密码

已经登录服务器时执行：

```bash
passwd root
```

root 密码只用于 ECS/SSH，不是网页密码。

`passwd root` 会要求输入两次新的 root 密码。修改 root 密码不会改变网页用户 `synthadmin` 的密码，也不会改变 LLM/Embedding API Key。

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

添加或删除公钥后恢复正确权限：

```bash
chown root:root /root/.ssh/authorized_keys
chmod 700 /root/.ssh
chmod 600 /root/.ssh/authorized_keys
```

- `chmod 700 /root/.ssh`：只有 root 能进入 SSH 配置目录；
- `chmod 600 authorized_keys`：只有 root 能读写允许登录的公钥清单；
- 不要把 SSH 私钥写入 `authorized_keys`，这里保存的只能是 `.pub` 公钥内容。

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
tail -n 200 /var/log/auth.log
```

Ubuntu 把 SSH 成功、失败和认证相关记录写入 `/var/log/auth.log`。`tail -n 200` 表示只显示最后 200 行，避免一次输出整个日志文件。

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
chown root:www-data /etc/nginx/.htpasswd-aiserver
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
tail -n 100 /var/log/auth.log
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

1. 当前使用 HTTP IP 访问，网页认证和业务内容没有 HTTPS 加密，不要在酒店等不可信网络中直接使用；优先通过可信 VPN 或后续配置 HTTPS。
2. 不要把 `configs/*.yaml`、网页密码、root 密码或私钥提交到公开 Git 仓库。
3. 修改 SSH 配置前保持一个已登录终端，修改后先执行 `sshd -t`。
4. 不要直接开放 `8080` 到公网。
5. 当前新系统没有部署 `mcp-server`；如以后重新部署 8000 端口服务，应限制调用来源或放在 Nginx 后面。
6. 定期更新 API 密钥和网页密码；root/SSH 优先使用密钥登录并关闭公网密码登录。
7. 安全组中的 SSH 22 端口只允许管理员当前公网 IP `/32`，不要长期使用 `0.0.0.0/0`。
8. 重要更新前同时保留代码镜像回滚点和持久化数据备份，并把备份下载到另一台设备。
