# -*- coding: utf-8 -*-
"""
报告层
=====
Streamlit 复盘报告生成器

每个结论可点回到对应信号、数据日期、口径。
"""

from typing import List, Dict




def render_sector_review(db, date: str, sector_decision: Dict):
    """渲染板块维度的每日复盘报告"""
    import streamlit as st
    st.set_page_config(page_title=f"复盘 {date}", layout="wide")
    st.title(f"📊 复盘报告 {date}")

    # ---------- 全局概览 ----------
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("活跃板块数", sector_decision.get('active_sectors', 0))
    col2.metric("总持仓股票", len(sector_decision.get('all_stocks', [])))
    col3.metric("总板块数", sector_decision.get('total_sectors', 0))
    col4.metric("复盘日期", date)

    st.divider()

    # ---------- 板块排名 ----------
    st.subheader("🏆 板块排名（按信号分）")
    sorted_sectors = sector_decision.get('sorted_sectors', [])
    sector_scores = sector_decision.get('sector_scores', {})

    sector_overview = []
    for rank, sector_name in enumerate(sorted_sectors, 1):
        s = sector_decision['sectors'].get(sector_name, {})
        decision = s.get('decision', 'watch')
        emoji = "🟢" if decision == 'buy' else ("🟡" if decision == 'hold' else "⚪")
        sector_overview.append({
            '排名': rank,
            '板块': sector_name,
            '决策': f"{emoji} {decision.upper()}",
            '信号均分': f"{s.get('avg_signal_score', 0):.4f}",
            '活跃度': f"{s.get('avg_activity', 0):.4f}",
            '股票数': len(s.get('stocks', []))
        })

    if sector_overview:
        st.dataframe(sector_overview, use_container_width=True, hide_index=True)
    else:
        st.info("暂无板块数据")

    st.divider()

    # ---------- 各板块详情 ----------
    st.subheader("📋 板块详情")
    sectors = sector_decision.get('sectors', {})

    tabs = st.tabs(list(sectors.keys())[:10])  # 最多显示10个tab

    for tab, (sector_name, res) in zip(tabs, list(sectors.items())[:10]):
        with tab:
            decision = res.get('decision', 'watch')
            st.markdown(f"**决策: {decision.upper()}** | 信号均分: {res.get('avg_signal_score', 0):.4f} | 活跃度: {res.get('avg_activity', 0):.4f}")

            stocks = res.get('stocks', [])
            if stocks:
                df_data = []
                for s in stocks:
                    breakdown = s.get('breakdown', {})
                    df_data.append({
                        '证券代码': s['stock_code'],
                        '信号分': f"{s['score']:.4f}",
                        '热点': f"{breakdown.get('topic', 0):.4f}",
                        '业绩': f"{breakdown.get('earnings', 0):.4f}",
                        '资金流': f"{breakdown.get('money_flow', 0):.4f}",
                        '产业链': f"{breakdown.get('industry', 0):.4f}",
                    })
                st.dataframe(df_data, use_container_width=True, hide_index=True)
            else:
                st.info(f"该板块无推荐股票，原因: {res.get('reason', 'N/A')}")

    st.divider()

    # ---------- 系统自评栏 ----------
    st.subheader("🔍 系统自评")
    backtest_metrics = sector_decision.get('backtest_metrics', {})
    if backtest_metrics:
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("总收益", f"{backtest_metrics.get('total_return', 0)*100:.2f}%")
        m_col2.metric("年化收益", f"{backtest_metrics.get('annual_return', 0)*100:.2f}%")
        m_col3.metric("最大回撤", f"{backtest_metrics.get('max_drawdown', 0)*100:.2f}%")
        m_col4.metric("交易次数", backtest_metrics.get('n_trades', 0))
    else:
        st.info("暂无回测数据，请先运行回测")

    st.divider()

    # ---------- 数据溯源 ----------
    st.subheader("📎 数据溯源")
    with st.expander("查看原始数据"):
        st.markdown(f"- 决策日期: `{date}`")
        st.markdown(f"- 数据口径: Tushare / 东方财富互动")
        st.markdown(f"- as_of 时点: `{date}`")
        st.markdown(f"- 活跃股定义: 近5日成交量放大 + 涨幅为正 + 波动率稳定")


def render_daily_review(db, date: str, decision: Dict):
    """渲染每日复盘报告"""
    import streamlit as st
    st.set_page_config(page_title=f"复盘 {date}", layout="wide")
    st.title(f"📊 复盘报告 {date}")

    # ---------- 决策概览 ----------
    col1, col2, col3 = st.columns(3)
    col1.metric("决策", decision.get('decision', 'N/A').upper())
    col2.metric("平均评分", f"{decision.get('avg_score', 0):.4f}")
    col3.metric("持仓数量", decision.get('n_stocks', 0))

    st.divider()

    # ---------- 持仓股票 ----------
    st.subheader("🎯 持仓股票")
    scores = decision.get('scores', [])
    if scores:
        df_data = []
        for s in scores:
            row = {
                '证券代码': s['stock_code'],
                '总分': f"{s['score']:.4f}",
                '热点得分': f"{s['breakdown'].get('topic', 0):.4f}",
                '业绩得分': f"{s['breakdown'].get('earnings', 0):.4f}",
                '资金流得分': f"{s['breakdown'].get('money_flow', 0):.4f}",
                '持有期(天)': s.get('holding_period', 5)
            }
            df_data.append(row)
        st.dataframe(df_data, use_container_width=True)
    else:
        st.info("当日无持仓建议")

    st.divider()

    # ---------- 系统自评栏 ----------
    st.subheader("🔍 系统自评")
    backtest_metrics = decision.get('backtest_metrics', {})
    if backtest_metrics:
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("总收益", f"{backtest_metrics.get('total_return', 0)*100:.2f}%")
        m_col2.metric("年化收益", f"{backtest_metrics.get('annual_return', 0)*100:.2f}%")
        m_col3.metric("最大回撤", f"{backtest_metrics.get('max_drawdown', 0)*100:.2f}%")
        m_col4.metric("交易次数", backtest_metrics.get('n_trades', 0))
    else:
        st.info("暂无回测数据")

    st.divider()

    # ---------- 可追溯链接 ----------
    st.subheader("📎 数据溯源")
    with st.expander("查看原始数据"):
        st.markdown(f"- 决策日期: `{date}`")
        st.markdown(f"- 数据口径: Tushare / 东方财富互动")
        st.markdown(f"- as_of 时点: `{date}`")


def render_factor_report(factor_name: str, ic: float, rankic: float,
                         equity_curve: List[Dict],
                         out_of_sample: bool = True):
    """渲染因子评估报告"""
    import streamlit as st
    st.set_page_config(page_title=f"因子: {factor_name}", layout="wide")
    st.title(f"📈 因子评估: {factor_name}")

    status = "✅ 样本外验证通过" if out_of_sample else "⚠️ 样本内验证"
    st.caption(status)

    col1, col2 = st.columns(2)
    col1.metric("IC", f"{ic:.4f}" if ic else "N/A")
    col2.metric("RankIC", f"{rankic:.4f}" if rankic else "N/A")

    st.divider()

    if equity_curve:
        import pandas as pd
        df = pd.DataFrame(equity_curve)
        st.line_chart(df.set_index('date')['value'])


def generate_markdown_report(decision: Dict, backtest_metrics: Dict,
                             factor_validations: List[Dict]) -> str:
    """生成 Markdown 格式复盘报告（供存档）"""
    date = decision.get('date', 'N/A')
    lines = [
        f"# 股票复盘报告 {date}",
        "",
        f"## 决策建议: {decision.get('decision', 'N/A').upper()}",
        f"- 平均评分: {decision.get('avg_score', 0):.4f}",
        f"- 持仓数量: {decision.get('n_stocks', 0)}",
        "",
        "## 持仓股票",
    ]

    for s in decision.get('scores', []):
        lines.append(
            f"- {s['stock_code']} | 总分: {s['score']:.4f} | "
            f"热点: {s['breakdown'].get('topic', 0):.4f} | "
            f"业绩: {s['breakdown'].get('earnings', 0):.4f}"
        )

    lines.extend(["", "## 回测指标", ""])
    lines.extend([
        f"- 总收益: {backtest_metrics.get('total_return', 0)*100:.2f}%",
        f"- 年化收益: {backtest_metrics.get('annual_return', 0)*100:.2f}%",
        f"- 最大回撤: {backtest_metrics.get('max_drawdown', 0)*100:.2f}%",
        f"- 交易次数: {backtest_metrics.get('n_trades', 0)}",
    ])

    lines.extend(["", "## 因子验证", ""])
    for fv in factor_validations:
        status = "✅" if fv.get('passed') else "❌"
        lines.append(
            f"{status} {fv['factor_name']} | IC: {fv.get('ic', 'N/A')} | "
            f"RankIC: {fv.get('rankic', 'N/A')}"
        )

    return "\n".join(lines)
