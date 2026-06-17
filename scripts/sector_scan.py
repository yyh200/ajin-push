#!/usr/bin/env python3
"""
板块全景扫描 — 每周四 15:30 推送
分析本周各板块表现、资金流向、轮动路线
"""
import sys, os, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    push_report, call_deepseek, today_str, bjt_hour, bjt_now,
    get_market_indices, get_gold_prices, get_us_markets,
    get_finance_news, fmt_news,
    fmt_pct, fmt_price, already_pushed_today
)

# ⏰ 时间窗口：周四 12:00-18:00（兼容延迟）
def main():
    # 防重复：今天已推送过就跳过
    if already_pushed_today("sector_scan.yml"):
        print(f"[SKIP] {today_str()} 板块扫描今天已推送")
        return

    hour = bjt_hour()
    if not (12 <= hour <= 18):
        print(f"[SKIP] BJT {hour}:00，不在板块扫描时段（12-18点），跳过")
        return

    print(f"[{today_str()}] 阿金板块全景扫描生成中...")

    # 1. 采集数据
    idx = get_market_indices()
    gold = get_gold_prices()
    us = get_us_markets()
    news_list = get_finance_news(20)

    print(f"  大盘: {len(idx)} | 黄金: {len(gold)} | 美股: {len(us)} | 新闻: {len(news_list)}")

    # 2. 构建数据摘要
    news_section = ""
    for n in news_list[:12]:
        src = n.get("source", "?")
        title = n.get("title", "")
        news_section += f"- [{src}] {title}\n"

    idx_section = ""
    for code, q in idx.items():
        name = q.get("display_name", code)
        price = fmt_price(q.get("price"))
        chg = fmt_pct(q.get("change_pct"))
        idx_section += f"  {name}: {price} ({chg})\n"

    gold_section = ""
    for k, v in gold.items():
        gold_section += f"  {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})\n"

    us_section = ""
    for name, q in us.items():
        us_section += f"  {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})\n"

    system_prompt = """你是阿金🪙，大哥的分析小弟。

你的任务是生成板块全景扫描报告，分析近期（以本周一为起点）的A股板块轮动情况。

输出要求：
1. 按三个阶段分析：恐慌/调整 → 修复/反弹 → 分化/确认
2. 每段列领涨板块+驱动逻辑+资金流向
3. 画出轮动路线图
4. 对照大哥持仓：黄金55%/有色16%/半导体7%/电网8.3%/金银珠宝7.2%/云计算2%
5. 列出踩中什么/错过什么
6. 板块强度排名（当前）
7. 结尾署名：— 阿金 🪙"""

    user_prompt = f"""今天是{today_str()}。本周板块数据如下：

【大盘数据】
{idx_section}

【黄金】
{gold_section}

【美股】
{us_section}

【本周财经新闻】
{news_section}

请生成板块全景扫描报告。"""

    report = call_deepseek(system_prompt, user_prompt)
    if not report:
        print("[ERROR] DeepSeek 返回为空，无法生成报告")
        return

    title = f"板块全景扫描 | {today_str()}"
    push_report(title, report)
    print(f"[OK] {title} 已推送")

if __name__ == "__main__":
    main()
