# coding: utf-8
import tkinter as tk
import pywencai
from tkinter import ttk
from datetime import datetime, timedelta, time
import re
from datetime import date
from ttkbootstrap import Style
import openpyxl
def show_home():
    clear_right_frame()
    #从D:\\stock\\tool\\data\\everyday_data.xlsx文件读取数据
    workbook = openpyxl.load_workbook('D:\\stock\\tool\\data\\everyday_data.xlsx')
    sheet = workbook['Sheet1']
    #读取F列的数据，并插入到文本框中
    for row in sheet.iter_rows(min_row=2, values_only=True):
        content_text.insert(tk.END, row[5])
        content_text.insert(tk.END, "\n")
    


def show_applications():
    clear_right_frame()

def show_import_data():
    clear_right_frame()

    formula_button = tk.Button(right_frame, text="选股公式", command=lambda label=content_label: show_import_data_content(label))
    formula_button.pack(pady=0,expand=True,fill=tk.BOTH, anchor='w')
def show_formula_results():
    clear_right_frame()
    for i in range(0,5):
        content_label = tk.Label(right_frame, text="", font=("Arial", 12))
        content_label.pack(pady=0,fill=tk.NONE, anchor='w')
        content_label.place(x=200*i, y=0)
        formula_button = tk.Button(right_frame, text="选股公式", command=lambda label=content_label: show_formula_content(label), padx=0, pady=0)
        formula_button.place(x=500*i, y=500)
        #print(res.iloc[0:6].iloc[i].iloc[0] + ":" + res.iloc[0:6].iloc[i].iloc[1])
def show_import_data_content(label):
    res1 = pywencai.get(query = "连续红k,创业板，7日内阴线<4个，7日内涨幅大于5%,七日内涨幅大于5%次数>=1,返回所属同花顺行业,非ST股,竞价涨幅排名前三")
    #print(res.iloc[0:6].iloc[0])
    res2 = pywencai.get(query = "昨日神奇九转卖出>=5 竞价金额>100万 创业板，今日09点25分的收盘价>今日09点24分到今日09点25分的区间最低价，7日内阴线<4个，7日内涨幅大于5%")
    if res1 is None:
        return
    data_list = []
    # 获取当前的日期和时间
    now = datetime.now()

    # 获取今天的日期
    today = date.today()

    # 如果当前时间早于9:25
    if now.time() < time(9, 25):
        # 使用昨天的日期
        date_str = (today - timedelta(days=1)).strftime("%Y%m%d")
    else:
        # 使用今天的日期
        date_str = today.strftime("%Y%m%d")
    num_rows, num_cols = res.shape
    for i in range(0,min(5,num_rows)):
        tmp ={}
        tmp["股票代码"] = (res.to_dict())["股票代码"][i]
        tmp["股票简称"] = (res.to_dict())["股票简称"][i]
        tmp["最新涨跌幅"] = (res.to_dict())["最新涨跌幅"][i]
        tmp["所属同花顺行业"] = (res.to_dict())["所属同花顺行业"][i]
        data_list.append(tmp)
    data_str = '\n'.join(str(item) for item in data_list)

    text_box = tk.Text(label, font=("Arial", 12))
    text_box.pack(pady=0, expand=True, fill=tk.BOTH)
    text_box.insert(tk.END, data_str)

    # 将要高亮显示的单词列表
    highlight_words = []
    for item in data_list:
        highlight_words.append(item["股票简称"])
        highlight_words.append(item["股票代码"])
        highlight_words.append(item["所属同花顺行业"])

    # 在文本中查找所有匹配的单词
    matches = re.findall('|'.join(highlight_words), data_str)

    # 遍历所有需要高亮显示的单词
    for word in highlight_words:
        start_index = "1.0"
        while True:
            # 查找下一个匹配的单词
            start_index = text_box.search(word, start_index, tk.END)
            if not start_index:
                break
            end_index = f"{start_index}+{len(word)}c"
            text_box.tag_configure("green_font", foreground="green")
            text_box.tag_add("green_font", start_index, end_index)
            # 更新开始索引以查找下一个匹配的单词
            start_index = end_index

def show_formula_content(label):
    res = pywencai.get(query='昨日神奇九转卖出>=5 今日竞价金额>100万 创业板，7日内阴线<4个，7日内涨幅大于5%，竞价涨幅从高到低排序,返回所属同花顺行业', sort_key='', sort_order='asc')
    if res is None:
        return
    data_list = []
    # 获取当前的日期和时间
    now = datetime.now()

    # 获取今天的日期
    today = date.today()

    # 如果当前时间早于9:25
    if now.time() < time(9, 25):
        # 使用昨天的日期
        date_str = (today - timedelta(days=1)).strftime("%Y%m%d")
    else:
        # 使用今天的日期
        date_str = today.strftime("%Y%m%d")
    num_rows, num_cols = res.shape
    for i in range(0,min(5,num_rows)):
        tmp ={}
        tmp["股票代码"] = (res.to_dict())["股票代码"][i]
        tmp["股票简称"] = (res.to_dict())["股票简称"][i]
        tmp["竞价涨幅排名"] = (res.to_dict())["竞价涨幅排名"+"["+date_str+"]"][i]
        tmp["竞价异动类型"] = (res.to_dict())["竞价异动类型"+"["+date_str+"]"][i]
        tmp["技术形态"] = (res.to_dict())["技术形态"+"["+date_str+"]"][i]
        tmp["所属同花顺行业"] = (res.to_dict())["所属同花顺行业"][i]
        data_list.append(tmp)
    data_str = '\n'.join(str(item) for item in data_list)

    text_box = tk.Text(label, font=("Arial", 12))
    text_box.pack(pady=0, expand=True, fill=tk.BOTH)
    text_box.insert(tk.END, data_str)

    # 将要高亮显示的单词列表
    highlight_words = []
    for item in data_list:
        highlight_words.append(item["股票简称"])
        highlight_words.append(item["股票代码"])
        highlight_words.append(item["所属同花顺行业"])
    # 在文本中查找所有匹配的单词
    matches = re.findall('|'.join(highlight_words), data_str)

    # 遍历所有需要高亮显示的单词
    for word in highlight_words:
        start_index = "1.0"
        while True:
            # 查找下一个匹配的单词
            start_index = text_box.search(word, start_index, tk.END)
            if not start_index:
                break
            end_index = f"{start_index}+{len(word)}c"
            text_box.tag_configure("green_font", foreground="green")
            text_box.tag_add("green_font", start_index, end_index)
            # 更新开始索引以查找下一个匹配的单词
            start_index = end_index

def clear_right_frame():
    for widget in right_frame.winfo_children():
        widget.pack_forget()
        widget.destroy()

# 创建主窗口
window = tk.Tk()
window.title("策略分析")
window.geometry("2560x1440")

# 使用 ttkbootstrap 主题
style = Style(theme='sandstone')
window = style.master

# 创建左侧边框
left_frame = ttk.Frame(window, width=200, relief=tk.RAISED)
left_frame.grid(row=0, column=0, sticky="ns", padx=10, pady=10)

# 创建按钮并添加到左侧边框
home_button = ttk.Button(left_frame, text="首\n页", command=show_home)
home_button.pack(pady=1, expand=True, fill=tk.BOTH)

applications_button = ttk.Button(left_frame, text="应\n用", command=show_applications)
applications_button.pack(pady=1, expand=True, fill=tk.BOTH)

import_data_button = ttk.Button(left_frame, text="导\n入\n数\n据", command=show_import_data)
import_data_button.pack(pady=1, expand=True, fill=tk.BOTH)

formula_results_button = ttk.Button(left_frame, text="公\n式\n结\n果", command=show_formula_results)
formula_results_button.pack(pady=1, expand=True, fill=tk.BOTH)

# 创建右侧内容框架
right_frame = ttk.Frame(window, relief=tk.SUNKEN)
right_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)

# Create the content text box
content_text = tk.Text(right_frame, font=("Arial", 12))
content_text.pack(pady=1, expand=True, fill=tk.BOTH)

# Create a vertical scrollbar
scrollbar = tk.Scrollbar(right_frame, command=content_text.yview)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Configure the text box to use the scrollbar
content_text.configure(yscrollcommand=scrollbar.set)

# Set the row and column weights
window.rowconfigure(0, weight=1)
window.columnconfigure(0, weight=0)
window.columnconfigure(1, weight=1)

# Run the main loop
window.mainloop()