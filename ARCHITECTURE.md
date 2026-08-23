# 股票分析工具架构说明

## 项目结构

```
stock/
├── README.md                 # 项目说明文档
├── ARCHITECTURE.md          # 架构说明文档
├── requirements.txt          # 项目依赖
├── run.py                   # 启动脚本
├── config/
│   ├── __init__.py
│   └── settings.py          # 配置文件
├── src/
│   ├── __init__.py
│   ├── main.py              # 主程序入口
│   ├── data/
│   │   ├── __init__.py
│   │   ├── stock_data.py    # 股票数据获取模块
│   │   └── excel_handler.py # Excel处理模块
│   ├── visualization/
│   │   ├── __init__.py
│   │   ├── kline_chart.py   # K线图绘制模块
│   │   └── gui.py          # GUI界面模块
│   └── utils/
│       ├── __init__.py
│       ├── helpers.py       # 工具函数
│       └── constants.py     # 常量定义
├── data/
│   └── everyday_data.xlsx   # 数据存储文件
├── output/
│   └── kline_charts/        # K线图输出目录
└── tests/
    ├── __init__.py
    └── test_helpers.py      # 测试文件
```

## 架构设计原则

### 1. 模块化设计
- **数据层 (Data Layer)**: `src/data/` - 负责数据获取、处理和存储
- **业务层 (Business Layer)**: `src/main.py` - 负责业务逻辑处理
- **展示层 (Presentation Layer)**: `src/visualization/` - 负责用户界面和数据可视化

### 2. 单一职责原则
每个模块只负责一个特定功能：
- `StockDataManager`: 股票数据获取
- `KLineDataManager`: K线数据获取
- `ExcelHandler`: Excel文件操作
- `KLineChartRenderer`: K线图绘制
- `KLineGUI`: 图形用户界面

### 3. 配置分离
- 所有配置参数集中在 `config/settings.py`
- 支持不同环境的配置
- 易于维护和修改

### 4. 错误处理
- 统一的异常处理机制
- 详细的错误日志记录
- 重试机制支持

### 5. 代码规范
- 遵循PEP 8编码规范
- 详细的文档字符串
- 类型提示支持

## 核心模块说明

### 配置模块 (config/)
- **settings.py**: 包含所有配置参数，如文件路径、查询条件、图表设置等

### 数据模块 (src/data/)
- **stock_data.py**: 
  - `StockDataManager`: 股票数据获取和管理
  - `KLineDataManager`: K线数据获取和管理
- **excel_handler.py**: 
  - `ExcelHandler`: Excel文件读写操作

### 可视化模块 (src/visualization/)
- **kline_chart.py**: 
  - `KLineChartRenderer`: K线图渲染器
  - `KLineChartGenerator`: K线图生成器
- **gui.py**: 
  - `KLineGUI`: 图形用户界面

### 工具模块 (src/utils/)
- **helpers.py**: 通用工具函数
- **constants.py**: 常量定义

### 主程序 (src/main.py)
- **StockAnalysisApp**: 应用主类，协调各个模块

## 主要改进

### 1. 代码结构优化
- 将原来的单一文件拆分为多个模块
- 每个模块职责明确，易于维护
- 支持单元测试

### 2. 配置管理
- 所有配置参数集中管理
- 支持不同环境的配置
- 易于修改和扩展

### 3. 错误处理
- 统一的异常处理机制
- 详细的错误日志
- 重试机制

### 4. 类型提示
- 添加了完整的类型提示
- 提高代码可读性和可维护性

### 5. 文档完善
- 详细的文档字符串
- 架构说明文档
- 使用说明

## 使用方法

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 运行程序
```bash
python run.py
```

### 3. 运行测试
```bash
python -m unittest tests.test_helpers
```

## 扩展性

### 1. 添加新的数据源
- 在 `src/data/` 下创建新的数据管理器
- 实现相应的接口

### 2. 添加新的图表类型
- 在 `src/visualization/` 下创建新的渲染器
- 继承基础渲染器类

### 3. 添加新的GUI功能
- 在 `src/visualization/gui.py` 中扩展GUI类
- 添加新的界面组件

### 4. 修改配置
- 在 `config/settings.py` 中添加新的配置项
- 在相应模块中使用配置

## 测试策略

### 1. 单元测试
- 测试工具函数
- 测试数据处理逻辑
- 测试配置加载

### 2. 集成测试
- 测试模块间协作
- 测试完整流程

### 3. 性能测试
- 测试大数据量处理
- 测试内存使用

## 部署

### 1. 开发环境
```bash
python run.py
```

### 2. 生产环境
```bash
# 打包为可执行文件
pyinstaller --onefile run.py
```

### 3. 配置文件
- 根据环境修改 `config/settings.py`
- 设置正确的文件路径和参数 