#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 · 午间持仓分析 —— 12:00 推送
覆盖：上午盘面、持仓表现、资金流向、下午预判
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    push_report, call_deepseek, today_str, bjt_hour,
    get_market_indices, get_all_holdings_nav, get_gold_prices,
    get_finance_news, fmt_news, trigger_workflow,
    fmt_pct, fmt_price, HOLDINGS,
)

# ============================================================
# 午间系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实。

大哥是A股中长期投资者，持仓如下：
- 博时黄金ETF联接C 002611 → 实物黄金(~55%)
- 南方有色金属ETF 512400 → 铜/金/铝/锂/稀土(~16.3%)
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~5.5%)
- 华夏电网设备ETF联接C 025857 → 电网设备(~8.3%)
- 前海开源金银珠宝A 001302 → ⚠️ 实质=黄金矿业(~7.2%)
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~2.0%)

你的任务是生成午间持仓分析，12:00推送到大哥微信。

输出要求和格式：
1. 简洁直接，不用废话
2. 数据先行，结论收尾
3. 涨用🔴(红色)，跌用🟢(绿色)
4. 每条重要新闻后附 🧠 持仓解读
5. 用 - • 符号列表，不要用表格
6. 结尾署名：— 阿金 🪙"""


def build_noon_prompt(indices: dict, holdings_nav: list, gold_data: dict, news_list: list) -> str:
    """构建午间分析 prompt"""
    # 大盘
    index_lines = []
    for code, q in indices.items():
        name = q.get("display_name", code)
        index_lines.append(f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    # 持仓
    holding_lines = []
    for h in holdings_nav:
        name = h.get("display_name", h.get("code"))
        nav_val = h.get("nav") or h.get("price")
        chg = h.get("change_pct") or h.get("est_change")
        date_tag = h.get("_stale_days", "")
        stale_mark = " ⚠️" if h.get("_stale") else ""
        holding_lines.append(f"- {name}({h['code']}): {fmt_price(nav_val)} ({fmt_pct(chg)}) {date_tag}{stale_mark}")

    # 黄金
    gold_lines = []
    for k, v in gold_data.items():
        gold_lines.append(f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})")

    news_text = fmt_news(news_list)

    prompt = f"""今天是 {today_str()}（{today_str()}为报告生成日期）。

【重要规则】以下持仓数据中，每条都标注了"数据日期"。如果某条数据日期不是今天（标记了⚠️），说明该基金净值尚未更新到今天，你必须在报告中明确说明"XX基金使用的是X月X日的数据"，不要假装它是今天的实时数据。

请生成午间持仓分析。

## 今日财经要闻（附持仓解读）
{news_text}

注意：结合以上新闻来分析上午盘面，重要新闻后标注 🧠 持仓影响。

## 上午盘面数据

### 大盘指数
{chr(10).join(index_lines) if index_lines else '（数据暂缺）'}

### 持仓表现（注意：⚠️标记的为非当日最新数据！）
{chr(10).join(holding_lines) if holding_lines else '（数据暂缺）'}

### 黄金价格
{chr(10).join(gold_lines) if gold_lines else '（数据暂缺）'}

## 大哥持仓结构
- 博时黄金ETF联接C 002611 — ~55%（核心仓位，中长期持有不短线操作）
- 南方有色金属ETF 512400 — ~16.3%（铜/金/铝/锂/稀土）
- 东方人工智能主题混合C 017811 — ~5.5%（🔴 实际=半导体设备100%）
- 华夏电网设备ETF联接C 025857 — ~8.3%
- 前海开源金银珠宝A 001302 — ~7.2%（实质=黄金矿业）
- 易方达云计算ETF联接C 017854 — ~2.0%（试仓，云计算/AI算力）

## 加仓纪律提醒
加仓三条件：①价格到位 ②逻辑成立 ③①②共振，缺一不可。

## 请严格按照以下板块生成：

1. 📊 **盘面总览** — 上午A股特征一句话 + 核心主线
2. 🔴 **持仓温度** — 各标的上午表现及原因简析
3. 💰 **资金动向** — 盘面资金结构简评 + 板块流向
4. 🧠 **新闻解读** — 今天重要新闻对持仓的影响
5. 🔮 **下午关注** — 下午需要盯的关键位/信号
6. 📋 **操作提示** — 是否触发加仓/减仓窗口
"""
    return prompt


def main():
    # ⏰ 时间窗口检查：只在 11:00-13:00（午间）生成午间分析
    hour = bjt_hour()
    if not (11 <= hour <= 13):
        print(f"[SKIP] 当前 BJT {hour}:00，不在午间时段（11-13点），跳过")
        return

    print(f"[{today_str()}] 阿金午间分析生成中...")

    print("[1/5] 获取大盘指数...")
    indices = get_market_indices()

    print("[2/5] 获取持仓净值...")
    holdings_nav = get_all_holdings_nav()

    print("[3/5] 获取黄金价格...")
    gold_data = get_gold_prices()

    print("[4/5] 获取财经新闻...")
    news_list = get_finance_news(max_items=10)

    print("[5/5] 调用 DeepSeek 生成午间分析...")
    prompt = build_noon_prompt(indices, holdings_nav, gold_data, news_list)
    report = call_deepseek(prompt, system_prompt=SYSTEM_PROMPT)

    if not report:
        # Fallback 纯数据版
        report = f"# 📊 阿金午间分析 | {today_str()}\n\n⚠️ AI分析暂不可用，数据快照：\n\n"
        report += "### 大盘\n"
        for code, q in indices.items():
            report += f"- {q.get('display_name', code)}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})\n"
        report += "\n### 持仓\n"
        for h in holdings_nav:
            nav_val = h.get("nav") or h.get("price")
            chg = h.get("change_pct") or h.get("est_change")
            report += f"- {h.get('display_name', h['code'])}: {fmt_price(nav_val)} ({fmt_pct(chg)})\n"
        report += "\n*午间完整分析将在AI恢复后推送*\n"

    title = f"📊 阿金午间分析 | {today_str()}"
    result = push_report(title, report)
    success = result.get("wechat", False)

    if success:
        print(f"[✓] 午间分析推送成功 (微信:{result['wechat']} 邮箱:{result.get('email', False)})")
    else:
        print("[⚠️] 午间分析微信推送失败，继续触发下游")

    # 无论推送成功与否，都触发自循环
    print("[+] 触发晚报(自循环)...")
    trigger_workflow("evening_report.yml")


if __name__ == "__main__":
    main()
