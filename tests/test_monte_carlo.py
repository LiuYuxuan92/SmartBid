"""蒙特卡洛模拟模块测试

测试分布拟合、中标概率单调性、最优区间计算、
超时处理和数据不足错误。
"""

import numpy as np
import pytest

from src.monte_carlo.distribution import CompetitorModel


class TestCompetitorModelFit:
    """Test distribution fitting logic."""

    def test_normal_data_fits_as_normal(self):
        """>=5 normal-distributed data points should fit as normal."""
        np.random.seed(42)
        data = np.random.normal(loc=0.85, scale=0.03, size=20).tolist()
        model = CompetitorModel("comp_A", data)
        assert model.distribution_type == "normal"
        assert model.distribution is not None

    def test_few_data_points_uses_uniform(self):
        """<5 data points should fall back to uniform distribution."""
        model = CompetitorModel("comp_B", [0.8, 0.85, 0.9])
        assert model.distribution_type == "uniform"

    def test_zero_data_points_uses_uniform(self):
        """Empty data should use uniform fallback."""
        model = CompetitorModel("comp_C", [])
        assert model.distribution_type == "uniform"

    def test_exactly_four_points_uses_uniform(self):
        """Exactly 4 data points should use uniform."""
        model = CompetitorModel("comp_D", [0.8, 0.82, 0.84, 0.86])
        assert model.distribution_type == "uniform"

    def test_exactly_five_points_fits_distribution(self):
        """Exactly 5 data points should attempt distribution fitting."""
        model = CompetitorModel("comp_E", [0.80, 0.82, 0.84, 0.86, 0.88])
        assert model.distribution_type in ("normal", "lognormal")


class TestCompetitorModelSample:
    """Test sampling behavior."""

    def test_sample_returns_correct_size(self):
        """sample(n) should return an array of length n."""
        np.random.seed(42)
        data = np.random.normal(loc=0.85, scale=0.03, size=20).tolist()
        model = CompetitorModel("comp_A", data)
        samples = model.sample(1000)
        assert isinstance(samples, np.ndarray)
        assert len(samples) == 1000

    def test_sample_single_value(self):
        """sample(1) should return array of length 1."""
        model = CompetitorModel("comp_B", [0.8, 0.85])
        samples = model.sample(1)
        assert len(samples) == 1

    def test_uniform_samples_within_bounds(self):
        """Uniform fallback samples should stay within industry bounds."""
        model = CompetitorModel("comp_C", [0.9], industry_min=0.7, industry_max=1.0)
        assert model.distribution_type == "uniform"
        samples = model.sample(5000)
        assert np.all(samples >= 0.7)
        assert np.all(samples <= 1.0)

    def test_uniform_custom_bounds(self):
        """Uniform fallback should respect custom industry bounds."""
        model = CompetitorModel("comp_D", [0.8, 0.9], industry_min=0.6, industry_max=0.95)
        samples = model.sample(5000)
        assert np.all(samples >= 0.6)
        assert np.all(samples <= 0.95)


class TestCompetitorModelDistributionType:
    """Test distribution_type attribute correctness."""

    def test_distribution_type_set_for_uniform(self):
        """distribution_type should be 'uniform' for <5 points."""
        model = CompetitorModel("comp_X", [0.8])
        assert model.distribution_type == "uniform"

    def test_distribution_type_set_for_fitted(self):
        """distribution_type should be 'normal' or 'lognormal' for >=5 points."""
        np.random.seed(123)
        data = np.random.normal(loc=0.85, scale=0.02, size=50).tolist()
        model = CompetitorModel("comp_Y", data)
        assert model.distribution_type in ("normal", "lognormal")

    def test_lognormal_data_can_fit_lognormal(self):
        """Lognormal-distributed data should potentially fit as lognormal."""
        np.random.seed(99)
        # Generate clearly lognormal data
        data = np.random.lognormal(mean=-0.2, sigma=0.1, size=100).tolist()
        model = CompetitorModel("comp_Z", data)
        # Either fit is acceptable; we just verify it completes without error
        assert model.distribution_type in ("normal", "lognormal")


import json
import os
import tempfile
import time
from unittest.mock import patch

from src.monte_carlo.simulator import (
    MonteCarloSimulator,
    PricePoint,
    SimulationInput,
    SimulationReport,
)
from src.exceptions import InsufficientDataError


class TestMonteCarloSimulatorWinProbMonotonicity:
    """Test that lower price yields higher win probability (monotonicity)."""

    def test_win_probability_monotonically_decreases_with_price(self, tmp_path):
        """Lower bid prices should generally yield higher win probabilities."""
        # Create historical data for competitors
        for comp in ["comp_A", "comp_B"]:
            data_file = tmp_path / f"{comp}.json"
            # Competitors bid around 85% of budget
            np.random.seed(42)
            ratios = np.random.normal(loc=0.85, scale=0.03, size=30).tolist()
            data_file.write_text(json.dumps(ratios))

        simulator = MonteCarloSimulator(data_dir=str(tmp_path))
        sim_input = SimulationInput(
            project_budget=100000.0,
            competitors=["comp_A", "comp_B"],
            iterations=5000,
        )
        report = simulator.simulate(sim_input)

        # Win probability should be non-increasing as price increases
        # Allow small tolerance for stochastic noise
        probabilities = [pp.win_probability for pp in report.price_points]
        violations = 0
        for i in range(len(probabilities) - 1):
            if probabilities[i + 1] > probabilities[i] + 0.05:
                violations += 1
        # Allow at most a few noise violations out of ~30 price points
        assert violations <= 3, (
            f"Win probability should generally decrease with price, "
            f"but found {violations} significant violations"
        )


class TestMonteCarloSimulatorInsufficientData:
    """Test InsufficientDataError when no historical data exists."""

    def test_raises_insufficient_data_error_no_file(self, tmp_path):
        """Should raise InsufficientDataError when competitor has no data file."""
        simulator = MonteCarloSimulator(data_dir=str(tmp_path))
        sim_input = SimulationInput(
            project_budget=100000.0,
            competitors=["nonexistent_competitor"],
            iterations=100,
        )
        with pytest.raises(InsufficientDataError):
            simulator.simulate(sim_input)

    def test_raises_insufficient_data_error_empty_file(self, tmp_path):
        """Should raise InsufficientDataError when data file has empty list."""
        data_file = tmp_path / "empty_comp.json"
        data_file.write_text(json.dumps([]))

        simulator = MonteCarloSimulator(data_dir=str(tmp_path))
        sim_input = SimulationInput(
            project_budget=100000.0,
            competitors=["empty_comp"],
            iterations=100,
        )
        with pytest.raises(InsufficientDataError):
            simulator.simulate(sim_input)


class TestMonteCarloSimulatorTimeout:
    """Test that timeout returns partial results."""

    def test_timeout_returns_partial_results(self, tmp_path):
        """Simulation should return is_partial=True when timed out."""
        # Create data
        data_file = tmp_path / "comp_slow.json"
        np.random.seed(42)
        ratios = np.random.normal(loc=0.85, scale=0.03, size=20).tolist()
        data_file.write_text(json.dumps(ratios))

        simulator = MonteCarloSimulator(data_dir=str(tmp_path))
        sim_input = SimulationInput(
            project_budget=100000.0,
            competitors=["comp_slow"],
            iterations=10000000,  # Very large to force timeout
        )
        # Use a very short timeout to force partial results
        report = simulator.simulate(sim_input, timeout=0.001)

        assert report.is_partial is True
        assert report.iterations_completed < sim_input.iterations
        assert report.iterations_completed > 0
        assert len(report.price_points) > 0


class TestMonteCarloSimulatorExecute:
    """Test that execute() returns a serializable dict."""

    def test_execute_returns_serializable_dict(self, tmp_path):
        """execute() should return a JSON-serializable dictionary."""
        # Create data for competitor
        data_file = tmp_path / "comp_exec.json"
        np.random.seed(42)
        ratios = np.random.normal(loc=0.85, scale=0.03, size=20).tolist()
        data_file.write_text(json.dumps(ratios))

        simulator = MonteCarloSimulator(data_dir=str(tmp_path))
        input_data = {
            "project_budget": 100000.0,
            "competitors": ["comp_exec"],
            "iterations": 1000,
        }
        result = simulator.execute(input_data, config={})

        # Verify it's a dict with expected keys
        assert isinstance(result, dict)
        assert "recommended_min" in result
        assert "recommended_max" in result
        assert "price_points" in result
        assert "confidence_interval_95" in result
        assert "iterations_completed" in result
        assert "is_partial" in result

        # Verify JSON-serializable
        serialized = json.dumps(result)
        assert isinstance(serialized, str)

        # Verify types
        assert isinstance(result["recommended_min"], float)
        assert isinstance(result["recommended_max"], float)
        assert isinstance(result["price_points"], list)
        assert isinstance(result["confidence_interval_95"], list)
        assert len(result["confidence_interval_95"]) == 2
        assert isinstance(result["iterations_completed"], int)
        assert isinstance(result["is_partial"], bool)
