#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 · GitHub Actions 推送套件 — 通用模块
功能：数据获取 + DeepSeek 报告生成 + Server酱推送
"""
import os
import json
import requests
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

# ============================================================
# 配置（从环境变量读取，由 GitHub Secrets 注入）
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-26d9c364962742809698b89ea80e897f")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "SCT349874TVE0djy2pbyv3urWRUvhpIx0h")
QQ_MAIL_ADDR = os.environ.get("QQ_MAIL_ADDR") or "2323624967@qq.com"
QQ_MAIL_AUTH_CODE = os.environ.get("QQ_MAIL_AUTH_CODE", "rorkhuzwzwiiecia")  # SMTP 授权码
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_URL = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"

# ============================================================
# 持仓常量（与大哥实际持仓同步，2026-06-29 更新 — 重大调仓！有色已清/新增5G）
# ============================================================
HOLDINGS = {
    "博时黄金ETF联接C": {"code": "002611", "type": "fund", "weight": 0.332},
    "东方人工智能主题混合C": {"code": "017811", "type": "fund", "weight": 0.203},
    "华夏电网设备ETF联接C": {"code": "025857", "type": "fund", "weight": 0.141},
    "易方达云计算ETF联接C": {"code": "017854", "type": "fund", "weight": 0.078},
    "华夏人工智能ETF联接C": {"code": "008586", "type": "fund", "weight": 0.045},
    "华夏中证5G通信ETF联接C": {"code": "008087", "type": "fund", "weight": 0.041},
    "南方纳斯达克100QDII C": {"code": "016453", "type": "fund", "weight": 0.022},
}

# ============================================================
# Server酱 · 推送到微信
# ============================================================
def push_to_wechat(title: str, desp: str) -> bool:
    """通过 Server酱 推送到大哥微信"""
    # Title 最长 128（Server酱限制）
    if len(title) > 128:
        title = title[:125] + "..."
    try:
        data = {"title": title, "desp": desp}
        resp = requests.post(SERVERCHAN_URL, data=data, timeout=20)
        result = resp.json()
        if result.get("code") == 0:
            print(f"[PUSH] 推送成功: {title[:30]}... (内容{len(desp)}字符)")
            return True
        else:
            print(f"[PUSH] 推送失败: code={result.get('code')} msg={result.get('message','')}")
            return False
    except Exception as e:
        print(f"[PUSH] 推送异常: {e}")
        return False


# ============================================================
# QQ邮箱 · 推送备份
# ============================================================
def push_to_email(subject: str, content: str) -> bool:
    """通过 QQ 邮箱 SMTP 发送报告作为备份（HTML格式，双端口自动重试）"""
    if not QQ_MAIL_AUTH_CODE:
        print("[EMAIL] 未配置 QQ_MAIL_AUTH_CODE，跳过邮件推送")
        return False

    import smtplib
    import time
    from email.mime.text import MIMEText
    from email.header import Header

    # 构建邮件内容
    html_content = content.replace("\n", "<br>")
    html_body = f"""<html><body style="font-family:'Microsoft YaHei',sans-serif;padding:20px;color:#333">
<div style="max-width:800px;margin:auto;background:#fff;border-radius:8px;padding:20px">
{html_content}
</div></body></html>"""
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = Header(subject, "utf-8")
    msg["From"] = QQ_MAIL_ADDR
    msg["To"] = QQ_MAIL_ADDR  # 发给自己

    # 尝试两种端口：465(SSL) 和 587(STARTTLS)，自动重试
    configs = [
        {"port": 465, "use_ssl": True,  "desc": "SSL 465"},
        {"port": 587, "use_ssl": False, "desc": "STARTTLS 587"},
    ]

    for cfg in configs:
        try:
            if cfg["use_ssl"]:
                server = smtplib.SMTP_SSL("smtp.qq.com", cfg["port"], timeout=15)
            else:
                server = smtplib.SMTP("smtp.qq.com", cfg["port"], timeout=15)
                server.starttls()
            server.login(QQ_MAIL_ADDR, QQ_MAIL_AUTH_CODE)
            server.sendmail(QQ_MAIL_ADDR, [QQ_MAIL_ADDR], msg.as_string())
            server.quit()
            print(f"[EMAIL] 邮件推送成功 ({cfg['desc']}): {subject[:30]}...")
            return True
        except Exception as e:
            print(f"[EMAIL] {cfg['desc']} 尝试失败: {e}")
            time.sleep(1)
            continue

    print("[EMAIL] 所有端口尝试均失败")
    return False


# ============================================================
# 数据获取 · 财经新闻（新浪财经）
# ============================================================
def get_finance_news(max_items: int = 12) -> list:
    """
    获取当天财经新闻列表
    来源：华尔街见闻(快讯+热门) + 新浪财经 + 新浪公告
    返回: [{"title": "...", "time": "...", "source": "..."}, ...]
    """
    seen = set()
    news = []
    UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    # 来源1：华尔街见闻 — 快讯（主力）
    try:
        url = "https://api-one.wallstcn.com/apiv1/content/lives?channel=global-channel&limit=15"
        resp = requests.get(url, headers={**UA, "Referer": "https://wallstreetcn.com/"}, timeout=8)
        data = resp.json()
        for item in data.get("data", {}).get("items", []):
            title = item.get("title", "") or item.get("content_text", "")[:100]
            ctime = item.get("display_time", "")
            if title and title not in seen:
                seen.add(title)
                news.append({"title": title.strip(), "time": ctime, "source": "华尔街见闻"})
    except Exception as e:
        print(f"[NEWS] 华尔街见闻快讯获取失败: {e}")

    # 来源2：华尔街见闻 — 热门深度
    try:
        url = "https://api-one.wallstcn.com/apiv1/content/articles/hot?period=all&limit=8"
        resp = requests.get(url, headers={**UA, "Referer": "https://wallstreetcn.com/"}, timeout=8)
        data = resp.json()
        for item in data.get("data", {}).get("day_items", []):
            title = item.get("title", "")
            ctime = item.get("display_time", "")
            if title and title not in seen:
                seen.add(title)
                news.append({"title": title.strip(), "time": ctime, "source": "华尔街见闻"})
    except Exception as e:
        print(f"[NEWS] 华尔街见闻深度获取失败: {e}")

    # 来源3：新浪财经快讯（补充）
    try:
        url = "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2516&knum=8"
        resp = requests.get(url, headers=UA, timeout=8)
        data = resp.json()
        for item in data.get("result", {}).get("data", []):
            title = item.get("title", "").strip()
            ctime = item.get("ctime", "")
            if title and title not in seen:
                seen.add(title)
                news.append({"title": title, "time": ctime, "source": "新浪财经"})
    except Exception as e:
        print(f"[NEWS] 新浪财经获取失败: {e}")

    # 来源4：新浪财经热门新闻（补充头条级新闻）
    try:
        resp = requests.get(
            "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&knum=8",
            headers=UA, timeout=8
        )
        data = resp.json()
        for item in data.get("result", {}).get("data", []):
            title = item.get("title", "").strip()
            ctime = item.get("ctime", "")
            if title and title not in seen:
                seen.add(title)
                news.append({"title": title, "time": ctime, "source": "新浪热门"})
    except Exception as e:
        print(f"[NEWS] 新浪热门获取失败: {e}")

    # 去重后按时间排序
    news.sort(key=lambda x: str(x.get("time", 0)), reverse=True)
    return news[:max_items]


def fmt_news(news_list: list) -> str:
    """格式化新闻列表为文本"""
    if not news_list:
        return "（暂无财经新闻数据）"
    lines = []
    for i, n in enumerate(news_list, 1):
        lines.append(f"{i}. {n['title']}")
    return "\n".join(lines)


# ============================================================
# 统一推送 · 微信 + 邮箱
# ============================================================
def push_report(title: str, content: str) -> dict:
    """同时推送微信和邮箱，返回各通道结果"""
    wechat_ok = push_to_wechat(title, content)
    email_ok = push_to_email(title, content)
    return {"wechat": wechat_ok, "email": email_ok}


def push_dual(title: str, wechat_desp: str, email_desp: str = None) -> dict:
    """
    双通道推送：微信推摘要摘要，邮箱推完整版
    - title: 标题（共用）
    - wechat_desp: 微信推送的摘要内容（精炼版）
    - email_desp: 邮箱推送的完整版内容（默认=wechat_desp）
    """
    if email_desp is None:
        email_desp = wechat_desp
    wechat_ok = push_to_wechat(title, wechat_desp)
    email_ok = push_to_email(title, email_desp)
    if email_desp != wechat_desp:
        print(f"[DUAL] 微信({len(wechat_desp)}字) + 邮箱({len(email_desp)}字)")
    return {"wechat": wechat_ok, "email": email_ok}


# ============================================================
# 自循环触发 · 解决GitHub Actions调度延迟
# 每次推送成功后触发下一次，形成链条
# ============================================================
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "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")

def trigger_workflow(workflow_name: str) -> bool:
    """通过 GitHub API 触发指定 workflow 的 workflow_dispatch"""
    url = f"https://api.github.com/repos/yyh200/ajin-push/actions/workflows/{workflow_name}/dispatches"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    try:
        resp = requests.post(url, headers=headers, json={"ref": "main"}, timeout=10)
        if resp.status_code == 204:
            print(f"[TRIGGER] ✅ 触发 {workflow_name} 成功")
            return True
        else:
            print(f"[TRIGGER] ❌ 触发 {workflow_name} 失败: {resp.status_code}")
            return False
    except Exception as e:
        print(f"[TRIGGER] 异常: {e}")
        return False


def already_pushed_today(workflow_name: str) -> bool:
    """检查今天是否已成功推送（防重复），含随机延迟防竞争条件"""
    import random, time
    # 随机延迟0.5-2秒，减少双触发竞争概率
    time.sleep(random.uniform(0.5, 2.0))

    try:
        url = f"https://api.github.com/repos/yyh200/ajin-push/actions/workflows/{workflow_name}/runs"
        params = {"per_page": 10}
        headers = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        if resp.status_code != 200:
            return False
        runs = resp.json().get("workflow_runs", [])
        today = today_str()
        for run in runs:
            started = run.get("run_started_at", "")
            conclusion = run.get("conclusion", "")
            if started.startswith(today):
                # 只认已完成的（success/failure），不认进行中的（防竞争条件）
                if conclusion in ("success", "failure", "completed"):
                    return True
        return False
    except:
        return False


# ============================================================
# 报告网页版 · 上传到GitHub并返回链接
# ============================================================
def upload_report_as_html(report_text: str, date_str: str, report_type: str = "daily") -> str:
    """
    把报告内容转为HTML，上传到GitHub仓库的reports/目录，
    返回可访问的网页链接。
    
    Args:
        report_text: 报告内容（Markdown格式）
        date_str: 日期字符串（如 "2026-06-30"）
        report_type: 报告类型（daily / portfolio）
    
    Returns:
        网页链接URL，失败返回空字符串
    """
    repo = "yyh200/ajin-push"
    branch = "main"
    
    # 拼接成简易HTML
    safe_text = report_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><title>阿金报告 {date_str}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
max-width:800px;margin:0 auto;padding:20px;color:#333;line-height:1.7}}
table{{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}}
th,td{{border:1px solid #ddd;padding:6px 10px;text-align:center}}
th{{background:#2c3e50;color:#fff}}
</style></head>
<body><pre style="white-space:pre-wrap;font-family:inherit;margin:0">{safe_text}</pre></body></html>"""
    
    path = f"reports/{date_str}-{report_type}.html"
    api_url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    
    # 检查文件是否已存在（获取SHA）
    sha = None
    resp = requests.get(api_url, headers=headers)
    if resp.status_code == 200:
        sha = resp.json().get("sha")
    
    import base64
    payload = {
        "message": f"report: {date_str} {report_type}",
        "content": base64.b64encode(html.encode("utf-8")).decode("utf-8"),
        "branch": branch,
    }
    if sha:
        payload["sha"] = sha
    
    resp2 = requests.put(api_url, headers=headers, json=payload)
    if resp2.status_code in (200, 201):
        url = f"https://github.com/{repo}/blob/{branch}/{path}"
        print(f"[REPORT] 网页版已上传: {url}")
        return url
    else:
        print(f"[REPORT] 上传失败: {resp2.status_code}")
        return ""


# ============================================================
# DeepSeek · AI 报告生成
# ============================================================
def call_deepseek(prompt: str, system_prompt: str = "",
                  max_tokens: int = 2048, temperature: float = 0.7) -> Optional[str]:
    """调用 DeepSeek API 生成分析内容"""
    if not DEEPSEEK_API_KEY:
        print("[LLM] 错误: DEEPSEEK_API_KEY 未设置")
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-chat",
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": False,
            },
            timeout=60,
        )
        result = resp.json()
        content = result["choices"][0]["message"]["content"]
        print(f"[LLM] 生成成功: {len(content)} chars")
        return content
    except Exception as e:
        print(f"[LLM] 调用异常: {e}")
        if 'result' in locals():
            print(f"[LLM] 响应原文: {resp.text[:500]}")
        return None


# ============================================================
# 数据获取 · 基金净值（天天基金 API）
# ============================================================
def get_fund_nav(fund_code: str) -> dict:
    """
    获取基金最新净值数据
    返回: {code, name, date, nav, acc_nav, change_pct}
    """
    url = f"http://api.fund.eastmoney.com/f10/lsjz"
    params = {
        "callback": "jQuery",
        "fundCode": fund_code,
        "pageIndex": 1,
        "pageSize": 5,
    }
    headers = {
        "Referer": "https://fund.eastmoney.com/",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        resp = requests.get(url, params=params, headers=headers, timeout=10)
        text = resp.text
        # 去掉 JSONP 包裹
        if text.startswith("jQuery"):
            text = text[text.find("(")+1:text.rfind(")")]
        data = json.loads(text)
        records = data["Data"]["LSJZList"]
        if not records:
            return {"code": fund_code, "error": "无数据"}

        latest = records[0]
        prev = records[1] if len(records) > 1 else None

        nav = float(latest["DWJZ"])
        acc_nav = float(latest["LJJZ"])
        date = latest["FSRQ"]

        change_pct = 0.0
        if prev:
            prev_nav = float(prev["DWJZ"])
            change_pct = round((nav - prev_nav) / prev_nav * 100, 2)
        name = data["Data"].get("SHORTNAME", fund_code)

        # 获取实时估值
        est_nav, est_change, est_time = None, None, None
        try:
            est_url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
            est_resp = requests.get(est_url, headers=headers, timeout=5)
            est_text = est_resp.text
            if "jsonpgz" in est_text:
                est_json = json.loads(est_text[est_text.find("(")+1:est_text.rfind(")")])
                est_nav = float(est_json.get("gsz", 0))
                est_change = float(est_json.get("gszzl", 0))
                est_time = est_json.get("gztime", "")
        except:
            pass

        result = {
            "code": fund_code,
            "name": name,
            "date": date,
            "nav": nav,
            "acc_nav": acc_nav,
            "change_pct": change_pct,
            "est_nav": est_nav,
            "est_change": est_change,
            "est_time": est_time,
        }
        return result
    except Exception as e:
        return {"code": fund_code, "error": str(e)}


# ============================================================
# 数据获取 · ETF/指数实时行情（新浪 API）
# ============================================================
def get_quote(codes: list) -> dict:
    """
    批量获取实时行情
    支持: sh/sz 前缀（A股），gb_ 前缀（美股）
    返回: {code: {name, price, change, change_pct, ...}}
    """
    prefix_map = {}
    reverse_map = {}  # full_code → original_code
    full_codes = []
    for c in codes:
        if c.startswith("sh") or c.startswith("sz") or c.startswith("gb_"):
            full_codes.append(c)
            # 已有前缀的代码不需要reverse_map，调用方会用相同前缀查询
        elif c.startswith("5") or c.startswith("6") or c.startswith("9"):
            # 5xxxx=上证ETF, 6xxxx=上证股票, 9xxxx=上证B股/科创板
            full_codes.append(f"sh{c}")
            prefix_map[c] = f"sh{c}"
            reverse_map[f"sh{c}"] = c
        else:
            full_codes.append(f"sz{c}")
            prefix_map[c] = f"sz{c}"
            reverse_map[f"sz{c}"] = c

    url = f"https://hq.sinajs.cn/list={','.join(full_codes)}"
    headers = {
        "Referer": "https://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0",
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        lines = resp.text.strip().split("\n")
        result = {}
        for line in lines:
            if not line.strip():
                continue
            try:
                # 格式: var hq_str_sh600519="贵州茅台,1800.00,1795.00,..."
                var_part = line.split("=")[0]
                raw_code = var_part.split("_")[-1].strip()
                data_part = line.split("\"")[1]
                fields = data_part.split(",")

                name = fields[0]
                
                # 美股 (gb_) 字段布局不同 — 用var_part判断, raw_code已被截断
                if "gb_" in var_part:
                    # 美股: [0]=名称, [1]=最新价, [2]=涨跌幅(%), [3]=时间, [4]=涨跌额
                    price = float(fields[1]) if fields[1] else 0
                    change_pct = float(fields[2]) if fields[2] else 0
                    change = float(fields[4]) if len(fields) > 4 and fields[4] else 0
                    open_price = float(fields[5]) if len(fields) > 5 and fields[5] else 0
                    high = float(fields[6]) if len(fields) > 6 and fields[6] else 0
                    low = float(fields[7]) if len(fields) > 7 and fields[7] else 0
                    prev_close = round(price - change, 2) if price and change else 0
                else:
                    # A股: [0]=名称, [1]=开盘, [2]=昨收, [3]=最新价, [4]=最高, [5]=最低
                    open_price = float(fields[1]) if fields[1] else 0
                    prev_close = float(fields[2]) if fields[2] else 0
                    price = float(fields[3]) if fields[3] else 0
                    change = round(price - prev_close, 2)
                    change_pct = round(change / prev_close * 100, 2) if prev_close else 0
                    high = float(fields[4]) if fields[4] else 0
                    low = float(fields[5]) if fields[5] else 0
                volume = float(fields[8]) if len(fields) > 8 and fields[8] else 0
                amount = float(fields[9]) if len(fields) > 9 and fields[9] else 0

                result[raw_code] = {
                    "code": raw_code,
                    "name": name,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "open": open_price,
                    "high": high,
                    "low": low,
                    "prev_close": prev_close,
                    "volume": volume,
                    "amount": amount,
                }
                # 同时用原始短代码做key，方便调用方查找
                orig_code = reverse_map.get(raw_code, raw_code)
                if orig_code != raw_code:
                    result[orig_code] = result[raw_code]
            except:
                continue
        return result
    except Exception as e:
        print(f"[QUOTE] 获取行情异常: {e}")
        return {}


# ============================================================
# 数据获取 · 大盘指数
# ============================================================
def get_market_indices() -> dict:
    """获取 A 股主要指数行情"""
    codes = ["sh000001", "sz399001", "sz399006", "sh000688", "sh000300"]
    quotes = get_quote(codes)
    # 修正可读名称
    name_map = {
        "000001": "上证指数", "399001": "深证成指",
        "399006": "创业板指", "000688": "科创50", "000300": "沪深300",
    }
    for code, q in quotes.items():
        if code in name_map:
            q["display_name"] = name_map[code]
    return quotes


# ============================================================
# 数据获取 · 持仓基金净值批量获取
# ============================================================
def get_all_holdings_nav() -> list:
    """获取所有持仓的最新净值（带数据日期标注，陈旧数据自动用实时估值替代）"""
    results = []
    today = today_str()
    today_short = today.replace("-", "")  # "20260602"
    for name, info in HOLDINGS.items():
        if info["type"] == "fund":
            nav = get_fund_nav(info["code"])
            nav["display_name"] = name
            # 标注数据新鲜度
            nav_date_raw = nav.get("date", "")
            nav_date = nav_date_raw.replace("-", "") if nav_date_raw else ""  # 统一格式
            est_nav = nav.get("est_nav")  # 实时估值
            est_change = nav.get("est_change")  # 实时估值涨跌幅
            
            if nav_date and est_nav and est_nav > 0:
                # 如果净值日期不是今天，用实时估值替代
                if nav_date < today_short:
                    nav["price"] = est_nav          # 用实时估值
                    nav["change_pct"] = est_change   # 用实时涨跌幅
                    nav["_stale"] = True
                    nav["_stale_days"] = f"(实时估值，最新净值日期: {nav_date_raw})"
                else:
                    nav["_stale"] = False
                    nav["_stale_days"] = ""
                    nav["price"] = nav.get("nav")    # 今天的数据，用实际净值
                    nav["change_pct"] = nav.get("change_pct")
            elif nav_date:
                if nav_date < today_short:
                    nav["_stale"] = True
                    nav["_stale_days"] = f"数据日期: {nav_date_raw}（无实时估值）"
                else:
                    nav["_stale"] = False
                    nav["_stale_days"] = ""
                    nav["price"] = nav.get("nav")
                    nav["change_pct"] = nav.get("change_pct")
            results.append(nav)
        elif info["type"] == "etf":
            # ETF 用实时行情
            quotes = get_quote([info["code"]])
            q = quotes.get(info["code"], {})
            results.append({
                "code": info["code"],
                "display_name": name,
                "price": q.get("price"),
                "change_pct": q.get("change_pct"),
                "name": q.get("name", ""),
            })
    return results


# ============================================================
# 数据获取 · 黄金价格（上海金 + 伦敦金）
# ============================================================
def get_gold_prices() -> dict:
    """获取黄金价格（人民币金 + COMEX）"""
    result = {}
    # 上海黄金交易所 AU9999
    try:
        url = "https://hq.sinajs.cn/list=au9999"
        headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        if "hq_str_au9999" in resp.text:
            raw = resp.text.split("\"")[1]
            if raw:  # 非空时才解析
                data = raw.split(",")
                result["shgold"] = {
                    "name": "上海金AU99.99",
                    "price": float(data[1]) if len(data) > 1 and data[1] else 0,
                    "change_pct": float(data[3]) if len(data) > 3 and data[3] else 0,
                }
    except Exception as e:
        print(f"[GOLD] 上海金获取失败: {e}")

    # COMEX 黄金期货
    try:
        url = "https://hq.sinajs.cn/list=hf_GC"
        headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        if "hq_str_hf_GC" in resp.text:
            data = resp.text.split("\"")[1].split(",")
            # 新浪hf_GC格式: [0]=最新价, [4]=最高, [5]=最低, [7]=昨收, [8]=开盘
            current = float(data[0]) if data[0] else 0
            prev_close = float(data[7]) if len(data) > 7 and data[7] else 0
            change_pct = round((current - prev_close) / prev_close * 100, 2) if prev_close else 0
            result["comex"] = {
                "name": "COMEX黄金",
                "price": current,
                "change_pct": change_pct,
            }
    except Exception as e:
        print(f"[GOLD] COMEX获取失败: {e}")

    return result


# ============================================================
# 数据获取 · 美元指数
# ============================================================
def get_dxy() -> Optional[float]:
    """获取美元指数（多源尝试）"""
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # 源1: Yahoo Finance DX-Y.NYB
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB"
        params = {"interval": "1d", "range": "2d"}
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        data = resp.json()
        meta = data["chart"]["result"][0]["meta"]
        return meta["regularMarketPrice"]
    except:
        pass
    
    # 源2: 新浪 hf_DINIW
    try:
        url = "https://hq.sinajs.cn/list=hf_DINIW"
        resp = requests.get(url, headers={**headers, "Referer": "https://finance.sina.com.cn"}, timeout=8)
        resp.encoding = "gbk"
        if "hq_str_hf_DINIW" in resp.text:
            data = resp.text.split("\"")[1]
            if data:
                return float(data.split(",")[0])
    except:
        pass
    
    return None


# ============================================================
# 数据获取 · 美国三大指数（新浪美股）
# ============================================================
def get_us_markets() -> dict:
    """获取美股三大指数"""
    codes = ["gb_ixic", "gb_dji", "gb_inx"]
    quotes = get_quote(codes)
    name_map = {
        "ixic": "纳斯达克", "dji": "道琼斯", "inx": "标普500",
    }
    result = {}
    for code, q in quotes.items():
        display = name_map.get(code, code)
        result[display] = q
    return result


# ============================================================
# 工具 · 格式化涨跌幅
# ============================================================
def fmt_pct(val, with_sign=True):
    """格式化涨跌幅，带颜色标记（文本）"""
    if val is None:
        return "N/A"
    # 近零处理
    if abs(val) < 0.005:
        return "0.00%"
    prefix = "+" if with_sign and val > 0 else ""
    return f"{prefix}{val:.2f}%"


def fmt_price(val):
    """格式化价格"""
    if val is None:
        return "N/A"
    return f"{val:.2f}"


def today_str():
    """获取今天日期字符串"""
    return datetime.now().strftime("%Y-%m-%d")


def bjt_hour() -> int:
    """获取当前北京时间的小时（用于时间窗口判断）"""
    BJT = timezone(timedelta(hours=8))
    return datetime.now(BJT).hour


def bjt_now():
    """获取当前北京时间"""
    BJT = timezone(timedelta(hours=8))
    return datetime.now(BJT)


def is_monday() -> bool:
    """判断今天是不是周一"""
    return bjt_now().weekday() == 0


if __name__ == "__main__":
    # 测试
    print("=" * 50)
    print("阿金 · 通用模块测试")
    print("=" * 50)

    # 测试基金净值
    print("\n[测试] 基金净值:")
    nav = get_fund_nav("002611")
    print(f"  博时黄金: {nav.get('date')} 净值{nav.get('nav')} {fmt_pct(nav.get('change_pct'))}")

    # 测试大盘
    print("\n[测试] 大盘指数:")
    indices = get_market_indices()
    for code, q in indices.items():
        print(f"  {q.get('display_name', code)}: {q.get('price')} {fmt_pct(q.get('change_pct'))}")

    # 测试黄金
    print("\n[测试] 黄金价格:")
    gold = get_gold_prices()
    for k, v in gold.items():
        print(f"  {v['name']}: {v.get('price')} {fmt_pct(v.get('change_pct'))}")

    # 测试美股
    print("\n[测试] 美股:")
    us = get_us_markets()
    for name, q in us.items():
        print(f"  {name}: {q.get('price')} {fmt_pct(q.get('change_pct'))}")
