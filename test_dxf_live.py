"""Live test: DXF Parser module with a programmatically created DXF file"""
import sys
import json
import logging

sys.path.insert(0, "D:/CADAI")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

import ezdxf
from pathlib import Path

# Step 1: Create a sample DXF file with known geometry
print("="*60)
print("Step 1: Creating sample DXF file...")
print("="*60)

dxf_dir = Path("D:/CADAI/data/demo_dxf")
dxf_dir.mkdir(parents=True, exist_ok=True)
dxf_path = dxf_dir / "test_building.dxf"

doc = ezdxf.new("R2010")
msp = doc.modelspace()

# Add a closed rectangle on WALL layer (10m x 20m = 200 sq meters)
msp.add_lwpolyline(
    [(0, 0), (20, 0), (20, 10), (0, 10)],
    close=True,
    dxfattribs={"layer": "WALL"}
)

# Add another closed polygon on FLOOR layer (5m x 5m = 25 sq meters)
msp.add_lwpolyline(
    [(2, 2), (7, 2), (7, 7), (2, 7)],
    close=True,
    dxfattribs={"layer": "FLOOR"}
)

# Add some LINE entities on AXIS layer
msp.add_line((0, 0), (20, 0), dxfattribs={"layer": "AXIS"})  # 20m
msp.add_line((0, 0), (0, 10), dxfattribs={"layer": "AXIS"})  # 10m

# Add an ARC on CURVE layer (半径5, 90度弧)
msp.add_arc(center=(10, 5), radius=5.0, start_angle=0, end_angle=90,
            dxfattribs={"layer": "CURVE"})

doc.saveas(str(dxf_path))
print(f"Created DXF: {dxf_path}")
print(f"  - WALL layer: 10x20m rectangle (area=200)")
print(f"  - FLOOR layer: 5x5m square (area=25)")
print(f"  - AXIS layer: 2 lines (20m + 10m = 30m)")
print(f"  - CURVE layer: 1 arc (r=5, 90deg)")

# Step 2: Run DXF Parser
print(f"\n{'='*60}")
print("Step 2: Running DXF Parser...")
print("="*60)

from src.dxf_parser.parser import DXFParser
from src.dxf_parser.quota_mapper import QuotaMapper

quota_mapper = QuotaMapper("D:/CADAI/data/quota_db.json")
parser = DXFParser(quota_mapper=quota_mapper)

result = parser.execute({"dxf_paths": [str(dxf_path)]}, {})

print(f"\nResults: {len(result['results'])} geometry items")
print(f"Total area: {result['total_area']} sq meters")
print(f"Total length: {result['total_length']} meters")
print(f"Warnings: {len(result['warnings'])}")

print(f"\n{'='*60}")
print("Geometry Results:")
print("="*60)
for r in result["results"]:
    print(f"  {r['region_id']:20s} | {r['entity_type']:12s} | {r['measurement_type']:6s} | {r['value']:>10.2f}")

# Step 3: Apply quota mapping
print(f"\n{'='*60}")
print("Step 3: Applying Quota Mapping...")
print("="*60)

enriched = quota_mapper.enrich_results(result["results"])
print(f"\n{'区域ID':<20s} | {'类型':<6s} | {'数值':>10s} | {'定额编码':<8s} | {'单价':>8s} | {'小计':>12s}")
print("-" * 80)
for r in enriched:
    subtotal = f"{r['subtotal']:>12.2f}" if r['subtotal'] else "      -     "
    unit_price = f"{r['unit_price']:>8.2f}" if r['unit_price'] else "    -   "
    print(f"  {r['region_id']:<20s} | {r['measurement_type']:<6s} | {r['value']:>10.2f} | {r['quota_code']:<8s} | {unit_price} | {subtotal}")

# Save
output_path = "D:/CADAI/output/dxf_test_result.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump({"geometry": result, "enriched": enriched}, f, ensure_ascii=False, indent=2)
print(f"\nSaved to {output_path}")
