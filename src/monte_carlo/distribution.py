"""分布拟合模块

负责为每个竞争对手基于历史投标比率拟合概率分布
（normal/lognormal，按BIC选择最优）。
数据量<5时使用行业范围 uniform 分布作为后备。
"""

import logging
from typing import Optional

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)


class CompetitorModel:
    """竞争对手定价行为模型"""

    def __init__(self, competitor_id: str, historical_ratios: list[float],
                 industry_min: float = 0.7, industry_max: float = 1.0):
        self.competitor_id = competitor_id
        self.historical_ratios = historical_ratios
        self.industry_min = industry_min
        self.industry_max = industry_max
        self.distribution = None
        self.distribution_type: Optional[str] = None
        self.fit()

    def fit(self) -> None:
        """拟合分布

        >= 5个数据点: 尝试normal和lognormal，选BIC最优
        < 5个数据点: 使用uniform(industry_min, industry_max)
        """
        if len(self.historical_ratios) < 5:
            self.distribution_type = "uniform"
            self.distribution = stats.uniform(
                loc=self.industry_min,
                scale=self.industry_max - self.industry_min
            )
            logger.info(
                "Competitor '%s': <5 data points (%d), using uniform distribution [%.2f, %.2f]",
                self.competitor_id, len(self.historical_ratios),
                self.industry_min, self.industry_max
            )
            return

        data = np.array(self.historical_ratios)

        # Fit normal
        norm_params = stats.norm.fit(data)
        norm_ll = np.sum(stats.norm.logpdf(data, *norm_params))
        norm_bic = -2 * norm_ll + 2 * np.log(len(data))  # k=2 params

        # Fit lognormal (requires positive data)
        if np.all(data > 0):
            lognorm_params = stats.lognorm.fit(data, floc=0)
            lognorm_ll = np.sum(stats.lognorm.logpdf(data, *lognorm_params))
            lognorm_bic = -2 * lognorm_ll + 3 * np.log(len(data))  # k=3 params
        else:
            lognorm_bic = float('inf')
            lognorm_params = None

        if lognorm_params is not None and lognorm_bic < norm_bic:
            self.distribution_type = "lognormal"
            self.distribution = stats.lognorm(*lognorm_params)
            logger.info("Competitor '%s': fitted lognormal (BIC=%.2f)", self.competitor_id, lognorm_bic)
        else:
            self.distribution_type = "normal"
            self.distribution = stats.norm(*norm_params)
            logger.info("Competitor '%s': fitted normal (BIC=%.2f)", self.competitor_id, norm_bic)

    def sample(self, n: int) -> np.ndarray:
        """从拟合分布中采样n个比率值"""
        if self.distribution is None:
            raise ValueError(f"Distribution not fitted for competitor '{self.competitor_id}'")
        return self.distribution.rvs(size=n)
