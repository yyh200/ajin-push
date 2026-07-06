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
    push_dual, call_deepseek, today_str, bjt_hour, bjt_now, is_monday,
    already_pushed_today, upload_report_as_html,
    get_market_indices, get_all_holdings_nav, get_gold_prices,
    get_us_markets, get_dxy, get_finance_news, fmt_news,
    fmt_pct, fmt_price, HOLDINGS,
)

# ============================================================
# 系统提示词
# ============================================================
SYSTEM_PROMPT = """你是阿金🪙，大哥的分析小弟，风格清亮务实、数据说话。

使用「投资罗盘 v6.9」流水线框架执行分析：Phase 0预检（含基金穿透+财报日历预警）→ Phase 1数据采集（含数据质量纪律：交叉验证/日期精确/价格核实 + 涨跌原因追踪 + 🔴三源新闻强制覆盖：东方财富+四大证券报+新浪财经）→ Phase 2七维诊断（D1-D7，含🔴海外联动率检查+D2财报验证+牛熊双面）→ Phase 3组合审查（含CPPI超限检查+交叉重叠）→ Phase 4情景推演（含黑天鹅+战术调整+减仓标准流程）→ Phase 5自批判（含确认偏误+涨跌原因遗漏检查+🔴预输出强制检查清单）。每个Phase不可跳过。

大哥是A股中长期投资者，当前持仓如下（2026-07-01 最新）：
- 博时黄金ETF联接C 002611 → 实物黄金(~32.0%)，保底层
- 东方人工智能主题混合C 017811 → 🔴 实际=半导体设备100%（前十大集中度86%），进攻层(~22.1%)
- 华夏电网设备ETF联接C 025857 → 电网设备(~13.5%)，进攻层
- 易方达云计算ETF联接C 017854 → 云计算/AI算力(~8.1%)，进攻层
- 华夏人工智能ETF联接C 008586 → AI指数ETF(~4.6%)，进攻层
- 华夏中证5G通信ETF联接C 008087 → ⚠️ 实际=CPO(~50%)+PCB(~30%)，进攻层(~3.9%)，⚠️出货接盘风险
- 南方纳斯达克100QDII C 016453 → 美股科技指数(~2.1%)，进攻层，限购50元/日
- 已清仓：南方有色金属ETF 512400（❌ 6/26清仓）
- 现金 ~13.6%

🔴 穿透后真实结构（必须识别）：
  表面7只基金 → 实际只有3个方向：黄金32% + 科技链52%（半导体+云+AI+5G/CPO+纳指）+ 电网14%

使用「投资罗盘 v6.15」流水线框架，新增规则：
- 🔴 附录K战术离场纪律：进攻层必须执行Step 1逻辑闸门→Step 2K1信号矩阵→Step 3冲突决策
- 🔴 持仓净值数据采集纪律：所有涨跌幅数据必须用实际净值序列验证，禁止凭记忆推算
- 🔴 输出模板深度标准版：按7/01报告标杆执行

输出要求：
1. 严格按 Phase 0→5 流水线顺序输出
2. 涨用🔴(红色)，跌用🟢(绿色)
3. 🔴 每个方向必须给出 🟢牛案和🔴熊案双面分析
4. 必须包含 D7 政策事件日历
5. 必须包含 Phase 5 自我批判（含确认偏误检查+涨跌原因遗漏检查+基金底层指数检查）
6. 报告第一部分必须是财经新闻解读，逐条标注 🧠 持仓影响
7. 🔴 数据质量纪律：关键价格数据必须标注来源，日期必须精确，不编造不估算
8. 🔴 涨跌原因追踪：持仓方向涨跌幅>3%必须单独查原因并写入报告（事件+贡献度+说明）
9. 🔴 新闻采集优先级：先搜持仓方向相关新闻，再搜宏观全局。必须从至少3个来源采集。
10. 🔴 海外联动率检查：判断海外事件对A股影响前，先查最近1个月实际联动率（强联动🟢/弱联动🟡/独立行情🔴）
11. 🔴 预输出检查：输出前逐项核对——①三源新闻 ②涨跌原因 ③海外联动率 ④基金穿透 ⑤牛熊双面 ⑥数据交叉验证 ⑦报告完整展示
12. 结尾署名：— 阿金 🪙

七维诊断 + 双面牛熊 + D7政策日历 + 数据质量纪律 + 涨跌原因追踪 + 海外联动率检查 + 确认偏误检查 + 预输出检查清单。一个都不准少。"""


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

## 大哥持仓穿透（2026-07-01 最新 🔴）
- 博时黄金ETF联接C 002611 — ~32.0%（保底层，实物黄金，6月-19%回调）
- 东方人工智能主题混合C 017811 — ~22.1%（🔴 实际=半导体设备，进攻层，最硬逻辑方向）
- 华夏电网设备ETF联接C 025857 — ~13.5%（进攻层，电网设备）
- 易方达云计算ETF联接C 017854 — ~8.1%（进攻层，云计算/AI算力）
- 华夏人工智能ETF联接C 008586 — ~4.6%（进攻层，AI指数ETF）
- 华夏中证5G通信ETF联接C 008087 — ~3.9%（⚠️ 实际=CPO+PCB，进攻层，出货接盘风险）
- 南方纳斯达克100QDII C 016453 — ~2.1%（进攻层，美股科技指数，限购50元/日）
- 现金 ~13.6%

## 投资纪律
- 中长期视角，不做短线止损
- 加仓三条件：①价格到位 ②逻辑成立 ③①②共振
- 三层止盈闸门：逻辑→情绪→结构
- 附录K战术离场纪律：进攻层适用（K1信号矩阵→缩量/放量破趋势/滞涨）
- 黄金链~32%穿透为战略配置，跌破关键位=打折加仓区
- 13.6%现金等待合适时机，不随意加仓，非农前按兵不动

## 请严格按照以下板块生成完整报告（不要跳过任何板块，不要偷懒）：

1. 📰 **今日财经要闻** — 逐条解读当天重大新闻，每条附 🧠 持仓影响分析。不许只列标题不分析
2. 📊 **今日盘面** — 大盘一句话定调 + 成交额 + 涨跌比 + 核心主线
3. 🔴 **持仓逐标分析** — 每个标的必须给出 🟢牛案和🔴熊案双面判断 + 三条件/三层闸门状态
4. 💰 **资金与情绪** — 主力资金流向 + 北向资金 + 情绪温度(0-100)
5. 🌍 **海外联动** — 隔夜美股 + COMEX + 10Y美债 + 关键海外事件
6. 📅 **政策日历(D7)** — 未来两周重要事件及逐条对持仓的影响评估
7. 🎯 **操作建议** — 逐标的操作指引 + 触发条件 + 整体仓位建议
8. ⚠️ **风险警示** — 当前最大的 3 个风险点及应对方案

注意：
- 📰 财经新闻板块必须结合当天新闻逐条分析，不要只列标题
- 每条重要新闻必须标注 🧠 对大哥持仓的影响
- 每条方向必须同时分析看多和看空的理由
- 不可只说利好不说利空
- 不要因为跌了就盲目喊加仓，也不要因为涨了就喊持有
- 数据日期必须标注清楚，⚠️ 标记的非今日数据必须特别说明"""

    return prompt


# ============================================================
# 主流程
# ============================================================
def main():
    hour = bjt_hour()
    if not (12 <= hour <= 22):
        print(f"[SKIP] BJT {hour}:00，跳过")
        return
    
    if already_pushed_today("portfolio_report.yml"):
        print(f"[SKIP] 持仓分析今天已推送")
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

    # 4. 双通道推送 + 网页版链接
    title = f"📊 阿金持仓分析 | {today_str()}"
    
    # 上传完整报告到GitHub，生成网页链接
    report_url = upload_report_as_html(report, today_str(), "portfolio")
    
    # 微信版：链接放头部 + 报告摘要
    wechat_ver = ""
    if report_url:
        wechat_ver = f"📖 完整报告：{report_url}\n\n━━━━━━━━━━━━━━━━\n\n"
    wechat_ver += report[:3000]
    if not report_url and len(report) > 3000:
        wechat_ver += "\n\n📧 完整报告已发送至QQ邮箱，请查收。如未收到，可在聊天记录中查看完整版。"
    
    result = push_dual(title, wechat_ver, report)
    if result.get("wechat", False):
        print(f"[✓] 微信推送成功 ({len(wechat_ver)}字)")
    else:
        print("[✗] 微信推送失败")
    if result.get("email", False):
        print(f"[✓] 邮箱推送成功 ({len(report)}字)")


if __name__ == "__main__":
    main()
