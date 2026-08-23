# 多策略股票筛选工具

这是一个基于 Python Tkinter 的桌面应用程序，用于管理和执行多个自定义股票筛选策略，并快速展示符合条件的股票列表。

## 主要功能

- **图形用户界面**：提供一个直观的图形界面，方便操作。
- **多策略管理**：支持同时运行多个筛选公式。
- **从Excel导入**：可以从固定的Excel文件路径 (`D:\stock\tool\stock\data\everyday_data.xlsx`) 导入筛选公式。
- **本地数据库查询**：从本地 `stock_data.db` SQLite数据库中执行查询。
- **结果可视化**：以列表形式清晰地展示所有符合条件的股票。
- **详细信息查看**：单击列表中的任一股票，即可查看其详细信息和命中了哪些筛选公式。
- **结果导出**：可以将筛选出的结果导出为CSV文件。

## 环境要求

- Python 3.x
- Pandas库
- Tkinter (通常是Python标准库的一部分)

您可以通过以下命令安装所需依赖：
```bash
pip install pandas
```

## 安装与设置

1.  **获取代码**：
    将项目文件放置在您的本地目录。

2.  **准备数据库文件**：
    - 项目需要一个名为 `stock_data.db` 的SQLite数据库文件，并将其放置在与 `multi_strage.py` 相同的根目录下。
    - 数据库中必须包含一个名为 `stock_data` 的表。
    - 筛选公式将在此表上执行，因此表中需要包含您公式里用到的所有字段（例如：`股票代码`, `股票简称`, `涨跌幅` 等）。

3.  **准备Excel公式文件**：
    - 项目会从一个**固定路径**读取筛选公式。请确保此文件存在：`D:\stock\tool\stock\data\everyday_data.xlsx`。
    - Excel文件应包含至少两列：`名称` (策略名称) 和 `公式` (具体的SQL WHERE子句)。

## 使用方法

直接运行主程序脚本即可启动应用：

```bash
python multi_strage.py
```

## 文件结构

```
.
├── multi_strage.py     # 主应用程序脚本
├── stock_data.db       # 股票数据SQLite数据库 (需用户自行提供)
└── README.md           # 本说明文件
```

---
*注意: `stock_data.db` 和 `D:\stock\tool\stock\data\everyday_data.xlsx` 是运行此应用的前提条件，请在使用前确保它们已准备就绪。*
