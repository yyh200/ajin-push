# 🪙 阿金 · 独立推送套件

> 不依赖本地电脑，通过 GitHub Actions 定时跑，关机也能推送到微信。

## 部署步骤（大哥跟着做，5分钟搞定）

### 第1步：创建 GitHub 仓库
1. 打开 https://github.com/new
2. 仓库名填：`ajin-push`（或你喜欢的名字）
3. 选 **Private**（私有仓库，持仓数据不公开）
4. 点 "Create repository"

### 第2步：上传文件
把 `github_actions/` 文件夹里的全部内容上传到仓库：
```
📁 你的仓库
 ├── .github/workflows/
 │   ├── morning_report.yml
 │   ├── noon_report.yml
 │   └── evening_report.yml
 ├── scripts/
 │   ├── common.py
 │   ├── morning_report.py
 │   ├── noon_report.py
 │   └── evening_report.py
 ├── requirements.txt
 └── README.md
```

### 第3步：配置 Secrets（关键！）
进入仓库 Settings → Secrets and variables → Actions → New repository secret：

| Secret 名称 | 值 | 获取方式 |
|:-----------|:---|:--------|
| `DEEPSEEK_API_KEY` | `sk-xxxxxxxxxxxx` | DeepSeek 官网 → API Keys |
| `SERVERCHAN_KEY` | `SCT349874TVE0djy2pbyv3urWRUvhpIx0h` | 已经有了 |
| `QQ_MAIL_ADDR` | `2323624967@qq.com` | 你的QQ邮箱地址 |
| `QQ_MAIL_AUTH_CODE` | `xxxxxxxxxxxx` | 见下方说明 |

⚠️ **DEEPSEEK_API_KEY 和 SERVERCHAN_KEY 必须配，缺任何一个推送会失败。**
ℹ️ **QQ_MAIL 可选配** — 配了之后每次报告也会发一份到邮箱做备份。

### 获取 QQ 邮箱授权码（选配）
1. 打开 https://mail.qq.com → 设置 → 账户
2. 找到「POP3/IMAP/SMTP服务」→ 点击「生成授权码」
3. 复制授权码填入 GitHub Secrets 的 `QQ_MAIL_AUTH_CODE`

### 第4步：启用 Actions
1. 进入仓库 Actions 页面
2. 会看到 3 个 workflow：早报 / 午间 / 晚报
3. 每个都可以点 "Run workflow" 手动测试一次

### 第5步：验证
点 "Run workflow" 手动跑一次早报 → 等1-2分钟 → 看微信有没有收到推送。收到就说明全通了。

---

## 定时时间
| 推送 | 时间(CST) | 工作日 |
|:----|:---------:|:-----:|
| 早报 | 08:55 | 周一至周五 |
| 午间 | 12:00 | 周一至周五 |
| 晚报 | 17:00 | 周一至周五 |

周末不推送（A股休市）。

## 注意事项
- 数据源为天天基金 + 新浪财经公开 API，无需额外付费
- DeepSeek API 消耗极低，几块钱能用好几个月
- 所有数据通过 GitHub Secrets 加密，不会泄露
- 如果某次推送失败，GitHub 会自动重试或发邮件通知
