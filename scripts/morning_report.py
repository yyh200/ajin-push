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
    push_report, call_deepseek, today_str, bjt_hour, is_monday,
    get_us_markets, get_gold_prices, get_dxy,
    get_finance_news, fmt_news,
    fmt_pct, fmt_price,
)

# ============================================================
# 早报系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实。

大哥是A股中长期投资者，持仓如下：
- 博时黄金ETF联接C 002611 → 实物黄金(~55%)
- 南方有色金属ETF 512400 → 铜/金/铝/锂/稀土(~16.3%)
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~5.5%)
- 华夏电网设备ETF联接C 025857 → 电网设备(~8.3%)
- 前海开源金银珠宝A 001302 → ⚠️ 实质=黄金矿业(~7.2%)
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~2.0%)

你的任务是生成开盘前瞻早报，08:55推送到大哥微信，让大哥开盘前知道外面发生了什么、今天该盯什么。

输出要求和格式：
1. 简洁直接，不用"很高兴为您服务"这类废话
2. 数据先行，结论收尾
3. 有态度，看空就是看空
4. 涨用🔴(红色)，跌用🟢(绿色)
5. 每条重大新闻后附 🧠 持仓解读 — "跟大哥的持仓有啥关系"
6. 用 - • 符号列表，不要用表格
7. 结尾署名：— 阿金 🪙"""


def build_morning_prompt(us_data: dict, gold_data: dict, dxy: float, news_list: list) -> str:
    """构建早报 prompt（周一自动切换为周末复盘+周前瞻模式）"""
    us_lines = []
    for name, q in us_data.items():
        us_lines.append(f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    gold_lines = []
    for k, v in gold_data.items():
        gold_lines.append(f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})")

    news_text = fmt_news(news_list)
    
    # 周一：周末复盘模式
    if is_monday():
        headline = f"今天是 {today_str()}（周一）。以下美股和黄金数据为上周五收盘数据，新闻为周末最新消息。请生成周末复盘+本周前瞻，重点说明：①周末重要新闻 ②周五收盘后到周一的情绪变化 ③本周需要关注的关键事件"
        sections = """
1. 🌙 **周末复盘** — 周五美股收盘+周末重要新闻+黄金状态
2. 🥇 **金价技术位** — 当前金价状态 + 本周关键支撑/压力位
3. 🔴 **本周焦点** — 本周最重要的 3-5 件大事/数据/事件，每条后附 🧠 持仓解读
4. 📋 **一句话扫一圈** — 全部 6 个持仓方向的快速判断，每条 1 句话
5. 📅 **本周日程** — 本周重要经济数据/事件/财报发布"""
    else:
        headline = f"今天是 {today_str()}，请生成开盘前瞻早报。"
        sections = """
1. 🌙 **隔夜海外** — 美股三大指数涨跌 + 美债收益率 + 美元指数 + 原油 + COMEX黄金
2. 🥇 **金价技术位** — 内外盘金价状态 + 关键支撑/压力位 + RSI判断
3. 🔴 **今日焦点** — 当日最重要的 3-5 件大事，每条后附 🧠 持仓解读
4. 📋 **一句话扫一圈** — 全部 6 个持仓方向的快速判断，每条 1 句话
5. 📅 **今日日程** — 今天的重要经济数据/事件/财报发布"""

    prompt = f"""{headline}

【重要】以下美股数据为上一个交易日（通常为上周五）收盘数据，黄金数据为最近可获取的行情。请在报告中明确标注每条数据的实际日期，不要让用户误以为是今天的实时数据。

## 财经要闻（附持仓解读）
{news_text}

注意：请结合以上新闻来生成早报，每条重要新闻后标注 🧠 对大哥持仓的影响。

## 市场数据

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

## 请严格按照以下板块生成：
{sections}
"""
    return prompt


def main():
    # ⏰ 时间窗口：7-13点（兼容GitHub schedule延迟）
    hour = bjt_hour()
    if not (7 <= hour <= 13):
        print(f"[SKIP] BJT {hour}:00，跳过")
        return

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
    else:
        print("[✗] 早报微信推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
