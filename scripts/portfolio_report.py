#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
阿金 14:45 全场持仓分析
每天 14:45 生成 → 14:50 推送微信
替代之前的早/午/晚三条推送
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import (
    push_report, call_deepseek, today_str, bjt_hour, bjt_now, is_monday,
    get_market_indices, get_all_holdings_nav, get_gold_prices,
    get_us_markets, get_dxy, get_finance_news, fmt_news,
    fmt_pct, fmt_price, HOLDINGS,
)

# ============================================================
# 系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实、数据说话。

大哥是A股中长期投资者，持仓如下：
- 博时黄金ETF联接C 002611 → 实物黄金(~55%)，保底层
- 南方有色金属ETF 512400 → 铜/金/铝/锂/稀土(~16%)，缓冲层
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%(~7%)，进攻层
- 华夏电网设备ETF联接C 025857 → 电网设备(~8.3%)，进攻层
- 前海开源金银珠宝A 001302 → ⚠️ 实质=黄金矿业(~7.2%)，缓冲层
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~2.0%)，进攻层试仓
- 现金 ~5%

你的任务：每天 14:45 生成全场持仓分析，推送到大哥微信。

输出要求：
1. 开门见山，数据先行，结论收尾
2. 涨用🔴(红色)，跌用🟢(绿色)
3. 用 - • 符号列表，不要用表格
4. 每条方向必须给出牛案和熊案双面分析
5. 若有基金净值不是今天的（⚠️标记），明确标注数据日期
6. 必须包含 D7 政策事件日历（6/18美联储等）
7. 结尾署名：— 阿金 🪙

分析框架（必须全部执行）：
1. 📊 今日盘面 — 大盘指数 + 核心主线
2. 🔴 持仓逐标分析 — 每个方向牛熊双面 + 三条件/三层闸门判定
3. 💰 资金与情绪 — 主力流向 + 北向 + 情绪温度
4. 🌍 海外联动 — 隔夜美股 + COMEX黄金 + 10Y美债 + 关键事件
5. 📅 政策日历(D7) — 未来两周重要事件及对持仓的影响
6. 🎯 操作建议 — 逐标指引 + 触发条件 + 整体仓位建议
7. ⚠️ 风险警示 — 当前最大的 3 个风险点"""


# ============================================================
# Prompt 构建
# ============================================================
def build_prompt(indices: dict, holdings_nav: list, gold_data: dict, us_data: dict, dxy, news_list: list) -> str:
    """构建 14:45 持仓分析 prompt"""
    # 大盘
    idx_lines = []
    for c, q in indices.items():
        idx_lines.append(f"- {q.get('display_name', c)}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    # 持仓（附数据日期标注）
    hold_lines = []
    for h in holdings_nav:
        name = h.get("display_name", h.get("code"))
        code = h.get("code")
        val = h.get("price") or h.get("nav")
        chg = h.get("change_pct") or 0
        date = h.get("date", "N/A")
        stale = h.get("_stale", False)
        tag = h.get("_stale_days", "")
        hold_lines.append(f"- {name}({code}): {fmt_price(val)} ({fmt_pct(chg)}) {tag}")

    # 黄金
    gold_lines = []
    for k, v in gold_data.items():
        gold_lines.append(f"- {v['name']}: {fmt_price(v.get('price'))} ({fmt_pct(v.get('change_pct'))})")

    # 美股
    us_lines = []
    for name, q in us_data.items():
        us_lines.append(f"- {name}: {fmt_price(q.get('price'))} ({fmt_pct(q.get('change_pct'))})")

    news_text = fmt_news(news_list)

    prompt = f"""今天是 {today_str()}（{today_str()}为报告生成日期，14:45盘中生成）。

【数据时效说明】以下数据中，大盘指数和ETF为实时行情，基金净值数据可能为上一交易日（⚠️标注的为非当日数据）。请在报告中明确标注每条数据的实际日期。

## 今日财经要闻
{news_text}

## 实时行情数据

### A股大盘
{chr(10).join(idx_lines)}

### 持仓数据
{chr(10).join(hold_lines)}

### 黄金
{chr(10).join(gold_lines)}

### 隔夜美股
{chr(10).join(us_lines)}

### 美元指数
{fmt_price(dxy) if dxy else '（数据暂缺）'}

## 大哥持仓穿透
- 博时黄金ETF联接C 002611 — ~55%（保底层）
- 南方有色金属ETF 512400 — ~16%（缓冲层，铜/金/铝/锂/稀土）
- 东方人工智能主题混合C 017811 — ~7%（🔴 实际=半导体设备，进攻层）
- 华夏电网设备ETF联接C 025857 — ~8.3%（进攻层）
- 前海开源金银珠宝A 001302 — ~7.2%（⚠️ 实质=黄金矿业，缓冲层）
- 易方达云计算ETF联接C 017854 — ~2.0%（云计算/AI算力，进攻层试仓）
- 现金 ~5%

## 投资纪律
- 中长期视角，不做短线止损
- 加仓三条件：①价格到位 ②逻辑成立 ③①②共振
- 三层止盈闸门：逻辑→情绪→结构
- 黄金链~62%穿透是战略核心配置
- 6/18美联储会议前按兵不动，现金留着等靴子落地

## 请严格按照以下板块生成完整报告（不要跳过任何板块，不要偷懒）：

1. 📊 **今日盘面** — 大盘一句话定调 + 成交额 + 涨跌比 + 核心主线
2. 🔴 **持仓逐标分析** — 每个标的必须给出 🟢牛案和🔴熊案双面判断 + 三条件/三层闸门状态
3. 💰 **资金与情绪** — 主力资金流向 + 北向资金 + 情绪温度(0-100)
4. 🌍 **海外联动** — 隔夜美股 + COMEX + 10Y美债 + 关键海外事件
5. 📅 **政策日历(D7)** — 未来两周重要事件及逐条对持仓的影响评估
6. 🎯 **操作建议** — 逐标的操作指引 + 触发条件 + 整体仓位建议
7. ⚠️ **风险警示** — 当前最大的 3 个风险点及应对方案

注意：
- 每条方向必须同时分析看多和看空的理由
- 不可只说利好不说利空
- 不要因为跌了就盲目喊加仓，也不要因为涨了就喊持有
- 数据日期必须标注清楚，⚠️ 标记的非今日数据必须特别说明
"""

    return prompt


# ============================================================
# 主流程
# ============================================================
def main():
    hour = bjt_hour()
    # 时间窗口：12-18点（兼容GitHub schedule延迟）
    if not (12 <= hour <= 18):
        print(f"[SKIP] 当前 BJT {hour}:00，不在分析时段（14-15点），跳过")
        return

    print(f"[{today_str()}] 阿金 14:45 持仓分析生成中...")

    # 1. 拉数据
    print("[1/6] 获取大盘指数...")
    indices = get_market_indices()

    print("[2/6] 获取持仓数据...")
    holdings_nav = get_all_holdings_nav()

    print("[3/6] 获取黄金价格...")
    gold_data = get_gold_prices()

    print("[4/6] 获取美股行情...")
    us_data = get_us_markets()

    print("[5/6] 获取财经新闻...")
    news_list = get_finance_news(max_items=12)

    # 2. DXY
    dxy = get_dxy()

    # 3. 构建 prompt 调用 DeepSeek
    print("[6/6] 调用 DeepSeek 生成分析...")
    prompt = build_prompt(indices, holdings_nav, gold_data, us_data, dxy, news_list)

    report = call_deepseek(prompt, system_prompt=SYSTEM_PROMPT, max_tokens=3000)
    if not report:
        print("[✗] 分析生成失败")
        return

    # 4. 推送
    title = f"📊 阿金持仓分析 | {today_str()}"
    result = push_report(title, report)
    if result.get("wechat", False):
        print(f"[✓] 推送成功")
    else:
        print("[✗] 推送失败")


if __name__ == "__main__":
    main()
