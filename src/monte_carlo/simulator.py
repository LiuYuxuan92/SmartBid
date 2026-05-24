"""蒙特卡洛模拟核心

负责执行 10,000+ 次迭代模拟竞争对手报价行为，
计算各价格点的中标概率，输出最优报价区间和95%置信区间。
超时120秒返回部分结果。
"""

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from src.exceptions import InsufficientDataError
from src.monte_carlo.distribution import CompetitorModel
from src.pipeline.orchestrator import BaseModule

logger = logging.getLogger(__name__)


@dataclass
class SimulationInput:
    project_budget: float
    competitors: list[str]
    iterations: int = 10000
    win_threshold: float = 0.6


@dataclass
class PricePoint:
    price: float
    win_probability: float


@dataclass
class SimulationReport:
    recommended_min: float
    recommended_max: float
    price_points: list[PricePoint]
    confidence_interval_95: tuple[float, float]
    iterations_completed: int
    is_partial: bool


class MonteCarloSimulator(BaseModule):
    """蒙特卡洛模拟器，计算最优报价区间。"""

    def __init__(self, data_dir: str = "data/historical_bids"):
        self.data_dir = Path(data_dir)

    @property
    def name(self) -> str:
        return "MonteCarlo"

    def validate_input(self, input_data: dict) -> bool:
        return "project_budget" in input_data and "competitors" in input_data

    def execute(self, input_data: dict, config: dict) -> dict:
        """执行模拟，返回可序列化的字典结果。"""
        sim_input = SimulationInput(
            project_budget=input_data["project_budget"],
            competitors=input_data["competitors"],
            iterations=input_data.get("iterations", 10000),
            win_threshold=input_data.get("win_threshold", 0.6),
        )
        report = self.simulate(sim_input)
        return {
            "recommended_min": report.recommended_min,
            "recommended_max": report.recommended_max,
            "price_points": [
                {"price": pp.price, "win_probability": pp.win_probability}
                for pp in report.price_points
            ],
            "confidence_interval_95": list(report.confidence_interval_95),
            "iterations_completed": report.iterations_completed,
            "is_partial": report.is_partial,
        }

    def _load_historical_data(self, competitor_id: str) -> list[float]:
        """从JSON文件加载竞争对手历史投标比率数据。"""
        file_path = self.data_dir / f"{competitor_id}.json"
        if not file_path.exists():
            return []
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Expect a list of bid ratios (bid_price / budget)
        if isinstance(data, list):
            return [float(x) for x in data]
        if isinstance(data, dict) and "ratios" in data:
            return [float(x) for x in data["ratios"]]
        return []

    def simulate(
        self, sim_input: SimulationInput, timeout: float = 120.0
    ) -> SimulationReport:
        """运行蒙特卡洛模拟。

        Args:
            sim_input: 模拟输入参数
            timeout: 超时秒数，默认120秒

        Returns:
            SimulationReport 包含最优报价区间和概率分布

        Raises:
            InsufficientDataError: 任一竞争对手无历史数据时抛出
        """
        start_time = time.time()
        budget = sim_input.project_budget
        iterations = sim_input.iterations
        threshold = sim_input.win_threshold

        # Build competitor models
        models: list[CompetitorModel] = []
        for comp_id in sim_input.competitors:
            ratios = self._load_historical_data(comp_id)
            if not ratios:
                raise InsufficientDataError(
                    f"No historical bid data found for competitor '{comp_id}'"
                )
            models.append(CompetitorModel(comp_id, ratios))

        # Price points: 1% increments from 70% to 100% of budget
        price_ratios = np.arange(0.70, 1.01, 0.01)
        prices = price_ratios * budget
        num_prices = len(prices)

        # Track wins per price point
        win_counts = np.zeros(num_prices, dtype=np.int64)
        iterations_completed = 0
        is_partial = False

        # Run iterations in batches for performance + timeout checks
        batch_size = min(1000, iterations)
        remaining = iterations

        first_batch = True
        while remaining > 0:
            # Check timeout (always run at least one batch)
            if not first_batch:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    is_partial = True
                    logger.warning(
                        "Simulation timed out after %.1fs with %d/%d iterations",
                        elapsed, iterations_completed, iterations,
                    )
                    break

            current_batch = min(batch_size, remaining)

            # Sample all competitors for this batch (vectorized)
            # Shape: (num_competitors, current_batch) - each value is a bid ratio
            competitor_samples = np.array(
                [model.sample(current_batch) for model in models]
            )
            # Convert ratios to absolute prices
            competitor_prices = competitor_samples * budget  # (num_competitors, batch)

            # Min competitor price per iteration
            min_competitor_prices = competitor_prices.min(axis=0)  # (batch,)

            # For each price point, count wins across this batch
            # Win = our_price < all competitor prices (i.e., our_price < min_competitor)
            for i, our_price in enumerate(prices):
                win_counts[i] += np.sum(our_price < min_competitor_prices)

            iterations_completed += current_batch
            remaining -= current_batch
            first_batch = False

        # Calculate win probabilities
        win_probabilities = win_counts / max(iterations_completed, 1)

        # Build price points list
        price_points = [
            PricePoint(price=float(prices[i]), win_probability=float(win_probabilities[i]))
            for i in range(num_prices)
        ]

        # Find optimal range where win_prob > threshold
        above_threshold = np.where(win_probabilities > threshold)[0]
        if len(above_threshold) > 0:
            recommended_min = float(prices[above_threshold[0]])
            recommended_max = float(prices[above_threshold[-1]])
        else:
            # No price meets threshold; recommend the best price point
            best_idx = int(np.argmax(win_probabilities))
            recommended_min = float(prices[best_idx])
            recommended_max = float(prices[best_idx])

        # 95% confidence interval based on the optimal range prices
        if len(above_threshold) > 0:
            optimal_prices = prices[above_threshold]
            ci_lower = float(optimal_prices[0])
            ci_upper = float(optimal_prices[-1])
        else:
            # Use the price with highest probability +/- small range
            best_idx = int(np.argmax(win_probabilities))
            ci_lower = float(prices[max(0, best_idx - 1)])
            ci_upper = float(prices[min(num_prices - 1, best_idx + 1)])

        confidence_interval_95 = (ci_lower, ci_upper)

        return SimulationReport(
            recommended_min=recommended_min,
            recommended_max=recommended_max,
            price_points=price_points,
            confidence_interval_95=confidence_interval_95,
            iterations_completed=iterations_completed,
            is_partial=is_partial,
        )
