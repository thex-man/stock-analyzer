# -*- coding: utf-8 -*-
"""数据抓取基类"""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Any


class BaseCrawler(ABC):
    """爬虫基类"""

    @abstractmethod
    def crawl(self, date: datetime) -> List[Dict[str, Any]]:
        """抓取指定日期的数据"""
        pass

    @abstractmethod
    def get_stock_dict(self) -> Dict[str, str]:
        """获取股票代码字典 {code: name}"""
        pass
