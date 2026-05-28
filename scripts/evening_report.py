#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 · 收盘晚报 + 持仓复盘 —— 17:00 推送
覆盖：收盘数据、持仓表现、资金面、公告扫雷、明日展望
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from common import (
    push_report, call_deepseek, today_str,
    get_market_indices, get_all_holdings_nav, get_gold_prices,
    get_finance_news, fmt_news, trigger_workflow,
    fmt_pct, fmt_price,
)

# ============================================================
# 晚报系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实。

大哥是A股中长期投资者，持仓如下：
- 博时黄金ETF联接C 002611 → 实物黄金(~55%)，保底层
- 南方有色金属ETF 512400 → 铜/金/铝/锂/稀土(~16.3%)
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~5.5%)
- 华夏电网设备ETF联接C 025857 → 电网设备(~8.3%)
- 前海开源金银珠宝A 001302 → ⚠️ 实质=黄金矿业(~7.2%)
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~2.0%)，试仓
- 现金 ~5.7%

你的任务是生成收盘复盘晚报，17:00推送到大哥微信。

输出要求和格式：
1. 简洁直接，不用"很高兴为您服务"这类废话
2. 数据先行，结论收尾
3. 有态度，看空就是看空
4. 涨用🔴(红色)，跌用🟢(绿色)
5. 每条重大新闻后附 🧠 持仓解读 — "跟大哥的持仓有啥关系"
6. 用 - • 符号列表，不要用表格
7. 结尾署名：— 阿金 🪙
8. 注意中长期持有视角：短期波动不等于卖出信号"""


def build_evening_prompt(indices: dict, holdings_nav: list, gold_data: dict, news_list: list) -> str:
    """构建晚报 prompt"""
    index_lines = []
    for code, q in indices.items():
        name = q.get("display_name", code)
        index_lines.append(f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    holding_lines = []
    for h in holdings_nav:
        name = h.get("display_name", h.get("code"))
        nav_val = h.get("nav") or h.get("price")
        chg = h.get("change_pct") or h.get("est_change")
        holding_lines.append(f"- {name}({h['code']}): {fmt_price(nav_val)} ({fmt_pct(chg)})")

    gold_lines = []
    for k, v in gold_data.items():
        gold_lines.append(f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})")

    news_text = fmt_news(news_list)

    prompt = f"""今天是 {today_str()}，请生成收盘复盘晚报。

## 今日财经要闻（附持仓解读）
{news_text}

注意：请结合以上新闻和大盘数据来生成晚报，每条重要新闻后标注 🧠 对大哥持仓的影响。

## 收盘数据

### 大盘指数
{chr(10).join(index_lines) if index_lines else '（数据暂缺）'}

### 持仓表现
{chr(10).join(holding_lines) if holding_lines else '（数据暂缺）'}

### 黄金价格
{chr(10).join(gold_lines) if gold_lines else '（数据暂缺）'}

## 大哥持仓穿透信息
- 博时黄金ETF联接C 002611 → 实物黄金(~55%)，保底层
- 南方有色金属ETF 512400 → 铜/金/铝/锂/稀土(~16.3%)，缓冲层
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~5.5%)，进攻层
- 华夏电网设备ETF联接C 025857 → 电网设备(~8.3%)，进攻层
- 前海开源金银珠宝A 001302 → ⚠️ 实质=黄金矿业(~7.2%)，缓冲层
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~2.0%)，进攻层试仓
- 现金 ~5.7%

## 投资纪律
- 中长期视角，不做短线止损
- 加仓三条件：①价格到位 ②逻辑成立 ③①②共振
- 黄金链~64%是战略核心配置

## 请严格按照以下板块生成：

1. 📊 **大盘收评** — 一句话定调 + 上证/深证/科创涨跌 + 成交额 + 涨跌比
2. 🔴 **持仓当日表现** — 逐个点评涨跌原因 + 组合加权收益估算
3. 💰 **资金面** — 北向资金 ±xx亿 + 板块资金流向（黄金/半导体/有色/电网）
4. 🌙 **海外盘前** — 美股期货/欧股/美债/原油/黄金盘前动态
5. 📋 **公告扫雷** — 持仓重仓股当日公告（减持/业绩/合同等）
6. 🔮 **明日关注** — 明天的重要事件/数据/技术位
"""
    return prompt


def main():
    print(f"[{today_str()}] 阿金晚报生成中...")

    print("[1/5] 获取收盘数据...")
    indices = get_market_indices()

    print("[2/5] 获取持仓数据...")
    holdings_nav = get_all_holdings_nav()

    print("[3/5] 获取黄金价格...")
    gold_data = get_gold_prices()

    print("[4/5] 获取财经新闻...")
    news_list = get_finance_news(max_items=10)

    print("[5/5] 调用 DeepSeek 生成晚报...")
    prompt = build_evening_prompt(indices, holdings_nav, gold_data, news_list)
    report = call_deepseek(prompt, system_prompt=SYSTEM_PROMPT)

    if not report:
        report = f"# 📊 阿金晚报 | {today_str()}\n\n⚠️ AI分析暂不可用，数据快照：\n\n"
        report += "### 大盘\n"
        for code, q in indices.items():
            report += f"- {q.get('display_name', code)}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})\n"
        report += "\n### 持仓\n"
        for h in holdings_nav:
            nav_val = h.get("nav") or h.get("price")
            chg = h.get("change_pct") or h.get("est_change")
            report += f"- {h.get('display_name', h['code'])}: {fmt_price(nav_val)} ({fmt_pct(chg)})\n"
        report += "\n*完整晚报将在AI恢复后推送*\n"

    title = f"📊 阿金晚报 | {today_str()}"
    result = push_report(title, report)
    success = result.get("wechat", False)

    if success:
        print(f"[✓] 晚报推送成功 (微信:{result['wechat']} 邮箱:{result.get('email', False)})")
        # 自循环：触发明天的早报
        print("[5/5] 触发明日早报(自循环)...")
        trigger_workflow("morning_report.yml")
    else:
        print("[✗] 晚报微信推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
