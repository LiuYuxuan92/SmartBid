"""Live test: Monte Carlo simulation with sample competitor data"""
import sys
import json
import logging
import numpy as np

sys.path.insert(0, "D:/CADAI")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from pathlib import Path

# Step 1: Create historical bid data for competitors
print("="*60)
print("Step 1: Creating competitor historical data...")
print("="*60)

data_dir = Path("D:/CADAI/data/historical_bids")
data_dir.mkdir(parents=True, exist_ok=True)

np.random.seed(42)

# Competitor A: aggressive bidder, typically bids 80-85% of budget
comp_a_ratios = np.random.normal(loc=0.82, scale=0.03, size=30).tolist()
(data_dir / "competitor_A.json").write_text(json.dumps(comp_a_ratios))

# Competitor B: conservative bidder, typically bids 88-93% of budget
comp_b_ratios = np.random.normal(loc=0.90, scale=0.025, size=25).tolist()
(data_dir / "competitor_B.json").write_text(json.dumps(comp_b_ratios))

# Competitor C: only 3 historical records (will use uniform fallback)
comp_c_ratios = [0.85, 0.87, 0.91]
(data_dir / "competitor_C.json").write_text(json.dumps(comp_c_ratios))

print(f"  competitor_A: 30 records, mean ratio={np.mean(comp_a_ratios):.3f}")
print(f"  competitor_B: 25 records, mean ratio={np.mean(comp_b_ratios):.3f}")
print(f"  competitor_C: 3 records (uniform fallback)")

# Step 2: Run Monte Carlo simulation
print(f"\n{'='*60}")
print("Step 2: Running Monte Carlo Simulation...")
print(f"  Project budget: 4,120,000 CNY (from crawler result)")
print(f"  Competitors: A, B, C")
print(f"  Iterations: 10,000")
print("="*60)

from src.monte_carlo.simulator import MonteCarloSimulator, SimulationInput

simulator = MonteCarloSimulator(data_dir=str(data_dir))
sim_input = SimulationInput(
    project_budget=4120000.0,  # From the real crawl result (412万)
    competitors=["competitor_A", "competitor_B", "competitor_C"],
    iterations=10000,
    win_threshold=0.6,
)

report = simulator.simulate(sim_input)

print(f"\n{'='*60}")
print("Simulation Results:")
print("="*60)
print(f"  Recommended price range: {report.recommended_min:,.0f} - {report.recommended_max:,.0f} CNY")
print(f"  Confidence interval (95%): {report.confidence_interval_95[0]:,.0f} - {report.confidence_interval_95[1]:,.0f} CNY")
print(f"  Iterations completed: {report.iterations_completed}")
print(f"  Partial results: {report.is_partial}")

print(f"\n  Price Points (win probability):")
print(f"  {'Price':>12s} | {'Win Prob':>8s} | {'Bar'}")
print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*30}")
for pp in report.price_points:
    bar = "█" * int(pp.win_probability * 30)
    marker = " ◀ OPTIMAL" if report.recommended_min <= pp.price <= report.recommended_max else ""
    print(f"  {pp.price:>12,.0f} | {pp.win_probability:>7.1%} | {bar}{marker}")

# Step 3: Save report
print(f"\n{'='*60}")
print("Step 3: Saving report...")
print("="*60)

report_data = {
    "project_budget": 4120000.0,
    "recommended_range": {
        "min": report.recommended_min,
        "max": report.recommended_max,
    },
    "price_points": [{"price": pp.price, "win_probability": pp.win_probability} for pp in report.price_points],
    "confidence_interval_95": list(report.confidence_interval_95),
    "iterations_completed": report.iterations_completed,
    "is_partial": report.is_partial,
}

output_path = "D:/CADAI/output/simulation_report.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(report_data, f, ensure_ascii=False, indent=2)
print(f"Saved to {output_path}")
