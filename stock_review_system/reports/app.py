#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Streamlit 复盘报告 Web 服务
=========================

用法:
  streamlit run app.py
"""

import streamlit as st
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from stock_review_system.config import DB_PATH
from stock_review_system.warehouse import WarehouseDB
from stock_review_system.engine import generate_decision
from stock_review_system.reports import render_daily_review, render_factor_report

# 默认参数
DEFAULT_DATE = datetime.now().strftime("%Y-%m-%d")

st.set_page_config(page_title="股票复盘决策系统", layout="wide")

st.title("📊 股票复盘决策系统")

# 侧边栏参数
st.sidebar.header("参数设置")
review_date = st.sidebar.date_input(
    "复盘日期",
    datetime.strptime(DEFAULT_DATE, "%Y-%m-%d")
)
concept = st.sidebar.text_input("概念板块", "AI")
n_stocks = st.sidebar.slider("持仓数量", 5, 50, 20)
run_review = st.sidebar.button("▶️ 生成复盘报告")

# 主界面
if run_review:
    db = WarehouseDB(str(DB_PATH))
    date_str = review_date.strftime("%Y-%m-%d")

    decision = generate_decision(
        db,
        review_date,
        concept=concept if concept else None
    )

    render_daily_review(db, date_str, decision)
else:
    st.info("👈 在左侧设置参数后点击『生成复盘报告』")
