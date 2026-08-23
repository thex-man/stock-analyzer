import pandas as pd
import pywencai
from datetime import datetime

def query_stocks(query_str, save_to_excel=False, filename=None):
    """
    使用同花顺问财接口查询股票数据

    :param query_str: 查询语句，例如 "今日停牌"
    :param save_to_excel: 是否将结果保存为Excel文件
    :param filename: 自定义保存文件名（不含后缀）
    :return: 包含查询结果的DataFrame
    """
    try:
        # 核心查询函数
        # 使用 loop=True 可以自动获取所有结果，避免分页限制[4,9](@ref)
        result = pywencai.get(
            query=query_str,        # 您的选股条件
            sort_key='股票代码',     # 按股票代码排序
            sort_order='asc',       # 升序排列
            loop=True,              # 获取全部数据
            perpage=100             # 每页尝试获取的最大条数（问财接口上限为100[2](@ref)）
        )
        
        if result is None or result.empty:
            print("未查询到相关数据。")
            return None
        
        # 数据清洗：确保股票代码为6位字符串格式
        if '股票代码' in result.columns:
            result['股票代码'] = result['股票代码'].astype(str).str.strip()
            # 如果代码包含市场后缀（如.SZ），可以提取前6位
            result['股票代码'] = result['股票代码'].str[:6]
        
        # 显示查询结果概览
        print(f"查询 '{query_str}' 成功！共找到 {len(result)} 条记录。")
        print("\n前5条结果如下：")
        print(result)
        
        # 保存结果到Excel
        if save_to_excel:
            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"问财查询结果_{timestamp}"
            file_path = f"{filename}.xlsx"
            result.to_excel(file_path, index=False, engine='openpyxl')
            print(f"\n结果已保存到文件：{file_path}")
        
        return result
        
    except Exception as e:
        print(f"查询过程中发生错误：{e}")
        return None

# 示例用法
if __name__ == "__main__":
    # 示例1：查询停牌股票[6](@ref)
    suspended_query = "停牌状态"
    df_suspended = query_stocks(suspended_query, save_to_excel=True, filename="今日停牌股票")