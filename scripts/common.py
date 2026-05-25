#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 · GitHub Actions 推送套件 — 通用模块
功能：数据获取 + DeepSeek 报告生成 + Server酱推送
"""
import os
import json
import requests
from datetime import datetime
from typing import Optional

# ============================================================
# 配置（从环境变量读取，由 GitHub Secrets 注入）
# ============================================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "sk-26d9c364962742809698b89ea80e897f")
SERVERCHAN_KEY = os.environ.get("SERVERCHAN_KEY", "SCT349874TVE0djy2pbyv3urWRUvhpIx0h")
QQ_MAIL_ADDR = os.environ.get("QQ_MAIL_ADDR", "2323624967@qq.com")
QQ_MAIL_AUTH_CODE = os.environ.get("QQ_MAIL_AUTH_CODE", "")  # SMTP 授权码
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
SERVERCHAN_URL = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"

# ============================================================
# 持仓常量（与大哥实际持仓同步，2026-05-25 更新）
# ============================================================
HOLDINGS = {
    "博时黄金ETF联接C": {"code": "002611", "type": "fund", "weight": 0.55},
    "南方有色金属ETF": {"code": "512400", "type": "etf", "weight": 0.163},
    "东方人工智能主题混合C": {"code": "017811", "type": "fund", "weight": 0.055},
    "华夏电网设备ETF联接C": {"code": "025857", "type": "fund", "weight": 0.083},
    "前海开源金银珠宝A": {"code": "001302", "type": "fund", "weight": 0.072},
    "易方达云计算ETF联接C": {"code": "017854", "type": "fund", "weight": 0.02},
}

# ============================================================
# Server酱 · 推送到微信
# ============================================================
def push_to_wechat(title: str, desp: str) -> bool:
    """通过 Server酱 推送到大哥微信"""
    try:
        data = {"title": title, "desp": desp}
        resp = requests.post(SERVERCHAN_URL, data=data, timeout=20)
        result = resp.json()
        if result.get("code") == 0:
            print(f"[PUSH] 推送成功: {title[:30]}...")
            return True
        else:
            print(f"[PUSH] 推送失败: {result}")
            return False
    except Exception as e:
        print(f"[PUSH] 推送异常: {e}")
        return False


# ============================================================
# QQ邮箱 · 推送备份
# ============================================================
def push_to_email(subject: str, content: str) -> bool:
    """通过 QQ 邮箱 SMTP 发送报告作为备份"""
    if not QQ_MAIL_AUTH_CODE:
        print("[EMAIL] 未配置 QQ_MAIL_AUTH_CODE，跳过邮件推送")
        return False

    import smtplib
    from email.mime.text import MIMEText
    from email.header import Header

    try:
        msg = MIMEText(content, "plain", "utf-8")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = QQ_MAIL_ADDR
        msg["To"] = QQ_MAIL_ADDR  # 发给自己

        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(QQ_MAIL_ADDR, QQ_MAIL_AUTH_CODE)
        server.sendmail(QQ_MAIL_ADDR, [QQ_MAIL_ADDR], msg.as_string())
        server.quit()
        print(f"[EMAIL] 邮件推送成功: {subject[:30]}...")
        return True
    except Exception as e:
        print(f"[EMAIL] 邮件推送异常: {e}")
        return False


# ============================================================
# 统一推送 · 微信 + 邮箱
# ============================================================
def push_report(title: str, content: str) -> dict:
    """同时推送微信和邮箱，返回各通道结果"""
    wechat_ok = push_to_wechat(title, content)
    email_ok = push_to_email(title, content)
    return {"wechat": wechat_ok, "email": email_ok}


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
    full_codes = []
    for c in codes:
        if c.startswith("sh") or c.startswith("sz") or c.startswith("gb_"):
            full_codes.append(c)
        elif c.startswith("6") or c.startswith("9"):
            full_codes.append(f"sh{c}")
            prefix_map[c] = f"sh{c}"
        else:
            full_codes.append(f"sz{c}")
            prefix_map[c] = f"sz{c}"

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
    """获取所有持仓的最新净值"""
    results = []
    for name, info in HOLDINGS.items():
        if info["type"] == "fund":
            nav = get_fund_nav(info["code"])
            nav["display_name"] = name
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
            data = resp.text.split("\"")[1].split(",")
            result["shgold"] = {
                "name": "上海金AU99.99",
                "price": float(data[1]) if data[1] else 0,
                "change_pct": float(data[3]) if len(data) > 3 and data[3] else 0,
            }
    except Exception as e:
        print(f"[GOLD] 上海金获取失败: {e}")

    # COMEX 黄金期货
    try:
        # 通过新浪外盘
        url = "https://hq.sinajs.cn/list=hf_GC"
        headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        if "hq_str_hf_GC" in resp.text:
            data = resp.text.split("\"")[1].split(",")
            result["comex"] = {
                "name": "COMEX黄金",
                "price": float(data[0]) if data[0] else 0,
                "change_pct": 0,
            }
            if len(data) > 2 and data[2]:
                result["comex"]["change_pct"] = float(data[2])
    except Exception as e:
        print(f"[GOLD] COMEX获取失败: {e}")

    return result


# ============================================================
# 数据获取 · 美元指数
# ============================================================
def get_dxy() -> Optional[float]:
    """获取美元指数"""
    try:
        url = "https://hq.sinajs.cn/list=hf_XAUUSD"  # 用黄金反向推有点绕
        # 改用美元指数
        url = "https://hq.sinajs.cn/list=hf_DINIW"
        headers = {"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "gbk"
        if "hq_str_hf_DINIW" in resp.text:
            data = resp.text.split("\"")[1].split(",")
            return float(data[0]) if data[0] else None
    except:
        return None
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
