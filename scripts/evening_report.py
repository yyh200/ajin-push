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
    fmt_pct, fmt_price,
)

# ============================================================
# 晚报系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析助手，风格清亮务实。
大哥是A股中长期投资者，核心持仓以黄金链为主(~64%)，持有现金等待加仓时机。

你的任务是生成收盘晚报+持仓复盘，17:00推送到大哥微信。

输出要求：
1. 先给今日盘面定调（一句话）
2. 逐标的复盘今日表现
3. 资金面和公告扫雷
4. 明日展望和关键观察点
5. 如有触发加仓/减仓条件，明确标注
6. 语言精炼，手机阅读友好
7. 注意中长期持有视角：短期波动不等于卖出信号"""


def build_evening_prompt(indices: dict, holdings_nav: list, gold_data: dict) -> str:
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

    prompt = f"""今天是 {today_str()}，请生成收盘晚报+持仓复盘。

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

## 观察标的（等加仓）
- （空 — 017854已于5/25建仓试仓）
- 中长期视角，不做短线止损
- 加仓三条件：①价格到位 ②逻辑成立 ③①②共振
- 黄金链~64%是战略核心配置，短期波动不操作
- 持有现金等待时机，不是逢跌就加

## 请生成
1. 【今日定调】一句话概括今天A股
2. 【持仓复盘】各标的表现简析（涨了为什么，跌了要不要紧）
3. 【资金简评】成交额、主力动向（如有数据）
4. 【公告扫雷】持仓重仓股有无异常公告/异动
5. 【技术位更新】各标的关键支撑/压力位
6. 【明日关注】明天需要盯的重点
7. 【操作信号】是否触发任何操作条件（加仓/减仓/持有）
"""
    return prompt


def main():
    print(f"[{today_str()}] 阿金晚报生成中...")

    print("[1/4] 获取收盘数据...")
    indices = get_market_indices()

    print("[2/4] 获取持仓数据...")
    holdings_nav = get_all_holdings_nav()

    print("[3/4] 获取黄金价格...")
    gold_data = get_gold_prices()

    print("[4/4] 调用 DeepSeek 生成晚报...")
    prompt = build_evening_prompt(indices, holdings_nav, gold_data)
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
    else:
        print("[✗] 晚报微信推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
