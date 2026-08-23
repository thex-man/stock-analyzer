import tkinter as tk
from tkinter import ttk, messagebox
import threading
import pywencai
import pandas as pd
import logging
from datetime import datetime

# 配置日志，用于记录程序运行状态
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class StockAnalyzerGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("股票数据分析工具")
        self.root.geometry("1000x700")
        
        # 设置中文字体
        self.style = ttk.Style()
        self.style.configure("Treeview.Heading", font=("SimHei", 10, "bold"))
        self.style.configure("Treeview", font=("SimHei", 10))
        self.style.configure("TButton", font=("SimHei", 10))
        self.style.configure("TLabel", font=("SimHei", 10))

        # GUI组件
        self.create_widgets()
        
        # 自动开始所有查询
        self.start_all_threads()
        
    def create_widgets(self):
        # 主框架
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 控制按钮和状态栏
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # 添加刷新按钮
        self.refresh_button = ttk.Button(control_frame, text="刷新数据", command=self.on_refresh)
        self.refresh_button.pack(side=tk.LEFT, padx=5)
        
        self.status_var = tk.StringVar(value="正在自动进行所有查询...")
        ttk.Label(control_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W).pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 结果显示框架
        results_frame = ttk.Frame(main_frame)
        results_frame.pack(fill=tk.BOTH, expand=True)

        # 文本结果显示框 (用于A, B功能)
        self.text_result_label = ttk.Label(results_frame, text="综合统计结果:", font=("SimHei", 12, "bold"))
        self.text_result_label.pack(anchor=tk.W, pady=(5, 0))
        self.text_result_box = tk.Text(results_frame, height=15, font=("SimHei", 10))
        self.text_result_box.pack(fill=tk.X, pady=(0, 10))
        
        # 表格结果显示 (用于C功能)
        self.tree_result_label = ttk.Label(results_frame, text="大幅回撤股票列表:", font=("SimHei", 12, "bold"))
        self.tree_result_label.pack(anchor=tk.W, pady=(5, 0))
        columns = ("股票代码", "股票简称")
        self.tree = ttk.Treeview(results_frame, columns=columns, show="headings")
        self.tree.column("股票代码", width=100, anchor=tk.CENTER)
        self.tree.column("股票简称", width=200, anchor=tk.CENTER)
        self.tree.heading("股票代码", text="股票代码")
        self.tree.heading("股票简称", text="股票简称")
        self.tree.pack(fill=tk.BOTH, expand=True)

    def _safe_update_ui(self, func, *args):
        """在主线程中安全地更新UI"""
        self.root.after(0, func, *args)

    def _set_status(self, message):
        self._safe_update_ui(self.status_var.set, message)
        
    def _clear_text_box(self):
        self._safe_update_ui(lambda: self.text_result_box.delete("1.0", tk.END))
        
    def _insert_text_box(self, text):
        self._safe_update_ui(lambda: self.text_result_box.insert(tk.END, text))

    def _clear_treeview(self):
        self._safe_update_ui(lambda: [self.tree.delete(item) for item in self.tree.get_children()])
        
    def _insert_treeview(self, item):
        self._safe_update_ui(lambda: self.tree.insert("", tk.END, values=item))
    
    def on_refresh(self):
        """刷新按钮点击事件处理"""
        # 禁用按钮防止重复点击
        self.refresh_button.config(state=tk.DISABLED)
        # 清空现有结果
        self._clear_text_box()
        self._clear_treeview()
        # 显示刷新状态
        self._set_status("正在刷新数据...")
        # 启动新线程执行刷新
        thread = threading.Thread(target=self._run_all_analyses)
        thread.start()
        
    def start_all_threads(self):
        """
        启动所有查询任务的线程
        """
        # 启动一个线程来执行所有查询
        thread = threading.Thread(target=self._run_all_analyses)
        thread.start()
    
    def _run_all_analyses(self):
        """
        按顺序运行所有分析任务
        """
        try:
            self._set_status("正在查询涨停破板率...")
            ztpb_rate, zhaban_count, zhangting_count = self.calculate_ztpb_rate()
            if ztpb_rate is not None:
                result_text = f"今日涨停破板率统计:\n"
                result_text += f"  炸板数量：{zhaban_count}\n"
                result_text += f"  涨停数量：{zhangting_count}\n"
                result_text += f"  破板率：{ztpb_rate:.2%}\n\n"
                self._insert_text_box(result_text)

            self._set_status("正在查询连板率统计...")
            lb_rates = self.calculate_lb_rate()
            if lb_rates:
                result_text = "连板率统计:\n"
                for key, value in lb_rates.items():
                    rate, success_count, base_count = value
                    if rate is not None:
                        result_text += f"  {key}：{rate:.2%} (成功: {success_count} / 基数: {base_count})\n"
                    else:
                        result_text += f"  {key}：查询失败\n"
                self._insert_text_box(result_text)
            
            self._set_status("正在查询大幅回撤股票...")
            pullback_stocks = self.get_major_pullback_stocks()
            
            self._clear_treeview()
            if not pullback_stocks.empty:
                for index, row in pullback_stocks.iterrows():
                    self._insert_treeview((row['股票代码'], row['股票简称']))
                self._set_status(f"所有查询完成，大幅回撤共找到 {len(pullback_stocks)} 只。")
            else:
                self._set_status("所有查询完成，未找到大幅回撤股票。")
        finally:
            # 无论成功失败，都重新启用刷新按钮
            self._safe_update_ui(lambda: self.refresh_button.config(state=tk.NORMAL))


    # --- 核心数据获取函数 ---
    def calculate_ztpb_rate(self):
        """计算今日涨停破板率。"""
        try:
            query_zhaban = "今日炸板;非ST;日期:今日"
            df_zhaban = pywencai.get(query=query_zhaban, loop=True)
            count_zhaban = len(df_zhaban) if df_zhaban is not None else 0

            query_zhangting = "今日涨停;非ST;日期:今日"
            df_zhangting = pywencai.get(query=query_zhangting, loop=True)
            count_zhangting = len(df_zhangting) if df_zhangting is not None else 0
            
            total_count = count_zhaban + count_zhangting
            rate = count_zhaban / total_count if total_count > 0 else 0.0
            
            return rate, count_zhaban, count_zhangting
        except Exception as e:
            logging.error(f"计算涨停破板率时发生错误: {e}")
            return None, None, None

    def calculate_lb_rate(self):
        """计算不同板数的连板率。"""
        results = {}
        try:
            # 功能1：二板连板率
            query_a = "上一个交易日首板涨停;非ST"
            df_a = pywencai.get(query=query_a, loop=True)
            count_a = len(df_a) if df_a is not None else 0
            query_b = "上一个交易日首板涨停且今日涨停;非ST"
            df_b = pywencai.get(query=query_b, loop=True)
            count_b = len(df_b) if df_b is not None else 0
            rate = count_b / count_a if count_a > 0 else 0.0
            results['二板连板率'] = (rate, count_b, count_a)
            
            # 功能2：三板连板率
            query_a = "上一个交易日二板涨停;非ST"
            df_a = pywencai.get(query=query_a, loop=True)
            count_a = len(df_a) if df_a is not None else 0
            query_b = "上一个交易日二板涨停且今日涨停;非ST"
            df_b = pywencai.get(query=query_b, loop=True)
            count_b = len(df_b) if df_b is not None else 0
            rate = count_b / count_a if count_a > 0 else 0.0
            results['三板连板率'] = (rate, count_b, count_a)
            
            # 功能3：高度板连板率
            query_a = "上一个交易日大于等于三板涨停;非ST"
            df_a = pywencai.get(query=query_a, loop=True)
            count_a = len(df_a) if df_a is not None else 0
            query_b = "上一个交易日大于等于三板涨停且今日涨停;非ST"
            df_b = pywencai.get(query=query_b, loop=True)
            count_b = len(df_b) if df_b is not None else 0
            rate = count_b / count_a if count_a > 0 else 0.0
            results['高度板连板率'] = (rate, count_b, count_a)
        except Exception as e:
            logging.error(f"计算连板率时发生错误: {e}")
        return results

    def get_major_pullback_stocks(self):
        """统计今日大幅回撤的股票。"""
        try:
            query = "（盘中最高价-收盘价）/收盘价>12%"
            df = pywencai.get(query=query, loop=True)
            print("df:", df)
            if df is None or df.empty:
                return pd.DataFrame()
            results = df[['股票代码', '股票简称']].copy()
            return results
        except Exception as e:
            logging.error(f"计算大幅回撤时发生错误: {e}")
            return pd.DataFrame()


if __name__ == "__main__":
    root = tk.Tk()
    app = StockAnalyzerGUI(root)
    root.mainloop()
