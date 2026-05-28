#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 · 每日财经早报 —— 08:55 推送
覆盖：隔夜美股、黄金、美债、当日日历、持仓影响前瞻
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    push_report, call_deepseek, today_str,
    get_us_markets, get_gold_prices, get_dxy,
    get_finance_news, fmt_news, trigger_workflow,
    fmt_pct, fmt_price,
)

# ============================================================
# 早报系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，一个专业的投资分析助手，风格清亮务实、数据说话。
你服务的用户是"大哥"，一位A股基金中长期投资者。
你的任务是生成一份简洁的每日早报，开盘前推送到大哥微信。

输出要求：
1. 开门见山，先说隔夜核心变化
2. 分板块分析：美股/黄金/美债美元
3. 给出从持仓角度看今天的关注重点
4. 当日关键日历（经济数据、事件）
5. 语言精炼，不要套话，每段3-4行
6. 格式用 Markdown，适合手机阅读"""


def build_morning_prompt(us_data: dict, gold_data: dict, dxy: float, news_list: list) -> str:
    """构建早报 prompt"""
    us_lines = []
    for name, q in us_data.items():
        us_lines.append(f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    gold_lines = []
    for k, v in gold_data.items():
        gold_lines.append(f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})")

    news_text = fmt_news(news_list)

    prompt = f"""今天是 {today_str()}，请生成今日早报。

## 今日财经要闻
{news_text}

## 隔夜市场数据

### 美股
{chr(10).join(us_lines) if us_lines else '（数据暂缺）'}

### 黄金
{chr(10).join(gold_lines) if gold_lines else '（数据暂缺）'}

### 美元指数
{fmt_price(dxy) if dxy else '（数据暂缺）'}

## 大哥持仓概况
- 博时黄金ETF联接C 002611 — ~55%（核心仓位）
- 南方有色金属ETF 512400 — ~16.3%
- 东方人工智能主题混合C 017811 — ~5.5%（实际=半导体设备）
- 华夏电网设备ETF联接C 025857 — ~8.3%
- 前海开源金银珠宝A 001302 — ~7.2%（实质=黄金矿业）
- 易方达云计算ETF联接C 017854 — ~2.0%（试仓，云计算/AI算力）

## 请生成以下内容
1. 【隔夜总览】一句话总结今晚到明早的核心变化
2. 【美股风向】三大指数涨跌及含义
3. 【黄金锚点】内外盘金价状态、关键位（上海金支撑/压力）
4. 【美债与美元】10Y美债和DXY方向对持仓的影响
5. 【持仓影响】各持仓标的今日的关注点
6. 【今日日历】当天重要经济数据/事件/财报
"""
    return prompt


def main():
    print(f"[{today_str()}] 阿金早报生成中...")

    # 1. 拉数据
    print("[1/5] 获取美股行情...")
    us_data = get_us_markets()

    print("[2/5] 获取黄金价格...")
    gold_data = get_gold_prices()

    print("[3/5] 获取美元指数...")
    dxy = get_dxy()

    print("[4/5] 获取财经新闻...")
    news_list = get_finance_news(max_items=10)

    # 2. 构建 prompt 调用 DeepSeek
    print("[5/5] 调用 DeepSeek 生成早报...")
    prompt = build_morning_prompt(us_data, gold_data, dxy, news_list)
    report = call_deepseek(prompt, system_prompt=SYSTEM_PROMPT)

    if not report:
        # Fallback: 如果 DeepSeek 失败，推送纯数据版
        report = f"# 📊 阿金早报 | {today_str()}\n\n"
        report += "⚠️ AI分析暂不可用，以下为数据快照：\n\n"
        report += "### 美股\n"
        for name, q in us_data.items():
            report += f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})\n"
        report += "\n### 黄金\n"
        for k, v in gold_data.items():
            report += f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})\n"
        if dxy:
            report += f"\n### 美元指数\n- DXY: {fmt_price(dxy)}\n"
        report += "\n*早报完整版将在AI恢复后推送*\n"

    # 3. 推送（微信 + 邮箱）
    title = f"📊 阿金早报 | {today_str()}"
    result = push_report(title, report)
    success = result.get("wechat", False)

    if success:
        print(f"[✓] 早报推送成功 (微信:{result['wechat']} 邮箱:{result.get('email', False)})")
        # 自循环：触发午间分析
        print("[5/5] 触发午间分析(自循环)...")
        trigger_workflow("noon_report.yml")
    else:
        print("[✗] 早报微信推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
