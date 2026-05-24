"""定额映射模块 - 图层名到定额编码的映射"""

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class QuotaMapper:
    """定额映射器 - 将DXF图层名映射到工程定额项"""

    def __init__(self, quota_db_path: str):
        self.quota_db = self._load_db(quota_db_path)

    def _load_db(self, path: str) -> dict:
        """加载定额数据库JSON文件
        
        Expected format:
        {
            "WALL": {"code": "A-001", "unit_price": 350.0, "unit": "m2", "description": "墙体工程"},
            "FLOOR": {"code": "A-002", "unit_price": 280.0, "unit": "m2", "description": "地面工程"},
            ...
        }
        """
        db_path = Path(path)
        if not db_path.exists():
            logger.warning("Quota database not found: %s, using empty mapping", path)
            return {}
        
        with open(db_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        return data if isinstance(data, dict) else {}

    def map(self, layer_name: str) -> Optional[dict]:
        """将图层名映射到定额项
        
        Args:
            layer_name: DXF图层名
            
        Returns:
            {code, unit_price, unit, description} dict if matched, None if unmatched
        """
        return self.quota_db.get(layer_name)

    def enrich_results(self, geometry_results: list[dict]) -> list[dict]:
        """为几何计算结果添加定额信息
        
        对每个结果:
        - 匹配到定额: 填入quota_code, unit_price, subtotal (value * unit_price)
        - 未匹配: quota_code="未匹配", unit_price=None, subtotal=None
        
        Args:
            geometry_results: GeometryResult字典列表
            
        Returns:
            enriched result list
        """
        enriched = []
        for result in geometry_results:
            layer = result.get("layer_name", "")
            quota_item = self.map(layer)
            
            if quota_item:
                result["quota_code"] = quota_item["code"]
                result["unit_price"] = quota_item["unit_price"]
                result["subtotal"] = round(result["value"] * quota_item["unit_price"], 2)
            else:
                result["quota_code"] = "未匹配"
                result["unit_price"] = None
                result["subtotal"] = None
            
            enriched.append(result)
        
        return enriched
