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
    push_dual, call_deepseek, today_str, bjt_hour, is_monday, already_pushed_today,
    get_us_markets, get_gold_prices, get_dxy,
    get_finance_news, fmt_news,
    fmt_pct, fmt_price,
)

# ============================================================
# 早报系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实。

大哥是A股中长期投资者，当前持仓如下（2026-06-26重大调仓后）：
- 博时黄金ETF联接C 002611 → 实物黄金(~33.2%)
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~20.3%)
- 华夏电网设备ETF联接C 025857 → 电网设备(~14.1%)
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~7.8%)
- 华夏人工智能ETF联接C 008586 → AI指数ETF(~4.5%)
- 华夏中证5G通信ETF联接C 008087 → ⚠️ 实际=CPO(~50%)+PCB(~30%)(~4.1%)
- 南方纳斯达克100QDII C 016453 → 美股科技指数(~2.2%)
- 已清仓：南方有色金属ETF 512400（❌）
- 现金 ~13.8%

🔴 穿透后真实结构：黄金33% + 科技链49%（半导体+云+AI+5G+纳指）+ 电网14%

你的任务是生成开盘前瞻早报，08:55推送到大哥微信。

🔴 新闻采集规则（v6.9框架）：
先搜持仓方向相关新闻：半导体/黄金/电网/云计算/AI/5G/纳指
再搜宏观全局新闻：FOMC/PCE/CPI/非农/地缘政治
至少从3个独立来源搜索（东方财富+四大证券报+新浪财经）

输出要求：
1. 📰 **隔夜要闻解读** — 逐条隔夜重要新闻，每条必须包含：①新闻核心内容 ②🧠对大哥持仓的具体影响（哪个方向+利好还是利空）。不允许只列标题不分析
2. 🌙 **隔夜海外全景** — 美股三大指数涨跌+美债收益率+美元指数+原油+COMEX黄金，每项带趋势判断
3. 🥇 **金价技术位** — 内外盘金价状态+关键支撑/压力位+RSI判断+1-2句多空分析
4. 🔴 **今日焦点** — 当日最重要的 3-5 件大事，每条后附 🧠 持仓解读，不可只列标题
5. 📋 **持仓扫一圈** — 全部 7 个方向逐个判断。**每个方向写2件事：①今日开盘前瞻判断（利多/利空/中性）②一句话理由。不要只写一句话敷衍**
6. 📅 **今日日程** — 今天的重要经济数据/事件/财报发布时间
7. 🔴 **海外联动率提示** — 如果隔夜美股半导体/费半大幅波动，不要默认A股必跟。先标注联动率评级
8. 结尾署名：— 阿金 🪙"""


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
1. 📰 **隔夜要闻解读** — 逐条分析隔夜/周末重要财经新闻，每条附 🧠 持仓影响。不���只列标题不分析
2. 🌙 **周末复盘** — 周五美股收盘+周末重要新闻+黄金状态
3. 🥇 **金价技术位** — 当前金价状态 + 本周关键支撑/压力位
4. 🔴 **本周焦点** — 本周最重要的 3-5 件大事/数据/事件，每条后附 🧠 持仓解读，不可只列标题
5. 📋 **持仓扫一圈** — 全部 7 个方向逐个判断：①开盘前瞻判断 ②一句话理由
6. 📅 **本周日程** — 本周重要经济数据/事件/财报发布"""
    else:
        headline = f"今天是 {today_str()}，请生成开盘前瞻早报。"
        sections = """
1. 🌙 **隔夜海外** — 美股三大指数涨跌 + 美债收益率 + 美元指数 + 原油 + COMEX黄金，每项带趋势判断
2. 🥇 **金价技术位** — 内外盘金价状态 + 关键支撑/压力位 + RSI判断
3. 🔴 **今日焦点** — 当日最重要的 3-5 件大事，每条后附 🧠 持仓解读，不可只列标题
4. 📋 **持仓扫一圈** — 全部 7 个方向逐个判断：①开盘前瞻判断 ②一句话理由。不要1句话敷衍
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

## 大哥持仓概况（2026-06-24 最新）
- 博时黄金ETF联接C 002611 — ~32.6%（核心仓位，实物黄金）
- 南方有色金属ETF 512400 — ~13.0%（铜/金/铝/锂/稀土）
- 东方人工智能主题混合C 017811 — ~9.7%（实际=半导体设备）
- 华夏电网设备ETF联接C 025857 — ~8.4%（电网设备）
- 易方达云计算ETF联接C 017854 — ~8.2%（云计算/AI算力）
- 南方纳斯达克100QDII C 016453 — ~2.1%（美股科技指数）
- 华夏人工智能ETF联接C 008586 — ~1.8%（AI指数ETF）
- 现金 ~24.0%

## 请严格按照以下板块生成：
{sections}
"""
    return prompt


def main():
    # ⏰ 时间窗口：7-13点
    hour = bjt_hour()
    if not (7 <= hour <= 13):
        print(f"[SKIP] BJT {hour}:00，跳过")
        return
    
    # 防重复：今天已推送过就跳过
    if already_pushed_today("morning_report.yml"):
        print(f"[SKIP] 早报今天已推送")
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

    # 3. 双通道推送：微信推摘要 + 邮箱推完整版
    title = f"📊 阿金早报 | {today_str()}"
    
    # 微信版：取前2500字作为摘要
    wechat_ver = report[:2500]
    if len(report) > 2500:
        wechat_ver += "\n\n📧 完整早报已发送至QQ邮箱，请查收。"
    
    result = push_dual(title, wechat_ver, report)
    success = result.get("wechat", False)
    
    if success:
        print(f"[✓] 早报推送成功 (微信:{result['wechat']} 邮箱:{result.get('email', False)})")
    else:
        print("[✗] 早报微信推送失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
