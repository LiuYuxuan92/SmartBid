"""招投标智能辅助系统 MVP - CLI入口"""

import sys
import argparse
import logging

from src.pipeline.config_loader import ConfigLoader
from src.pipeline.orchestrator import PipelineOrchestrator
from src.crawler.crawler_module import CrawlerModule
from src.dxf_parser.parser import DXFParser
from src.dxf_parser.quota_mapper import QuotaMapper
from src.monte_carlo.simulator import MonteCarloSimulator
from src.exceptions import ConfigError


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="招投标智能辅助系统 MVP"
    )
    parser.add_argument("project_id", help="项目标识符")
    parser.add_argument("--platforms", nargs="*", help="覆盖配置的目标平台列表")
    parser.add_argument("--dxf-paths", nargs="*", help="DXF文件路径列表")
    parser.add_argument(
        "--iterations", type=int, default=10000,
        help="蒙特卡洛模拟迭代次数 (1,000-1,000,000, default: 10,000)"
    )
    parser.add_argument("--config", default=None, help="配置文件路径")
    return parser.parse_args(argv)


def validate_iterations(iterations: int) -> int:
    if iterations < 1000 or iterations > 1000000:
        print(f"Error: --iterations must be between 1,000 and 1,000,000, got {iterations}", file=sys.stderr)
        sys.exit(1)
    return iterations


def main(argv=None):
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    args = parse_args(argv)
    validate_iterations(args.iterations)

    # Load config
    try:
        loader = ConfigLoader(args.config)
        config = loader.load()
    except ConfigError as e:
        print(f"Configuration error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Failed to load configuration: {e}", file=sys.stderr)
        sys.exit(1)

    # Override platforms if specified
    if args.platforms:
        config.setdefault("crawler", {})["target_platforms"] = [
            {"url": url, "name": url, "parser": "BaseParser"} for url in args.platforms
        ]

    # Override iterations
    config.setdefault("monte_carlo", {})["iterations"] = args.iterations

    # Create output directory (validate writable)
    from pathlib import Path
    output_base = config.get("pipeline", {}).get("output_base", "D:/CADAI/output")
    try:
        Path(output_base).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"Cannot create output directory '{output_base}': {e}", file=sys.stderr)
        sys.exit(1)

    # Build pipeline
    orchestrator = PipelineOrchestrator(config)

    # Register modules
    orchestrator.register_module(CrawlerModule())

    quota_db_path = config.get("dxf_parser", {}).get("quota_db_path", "data/quota_db.json")
    quota_mapper = QuotaMapper(quota_db_path)
    orchestrator.register_module(DXFParser(quota_mapper=quota_mapper))

    # RAG Generator would be registered here in production
    # orchestrator.register_module(RAGGeneratorModule(...))

    data_dir = "data/historical_bids"
    orchestrator.register_module(MonteCarloSimulator(data_dir=data_dir))

    # Inject DXF paths into initial input if provided
    initial_input = {}
    if args.dxf_paths:
        initial_input["dxf_paths"] = args.dxf_paths

    # Execute
    result = orchestrator.execute(args.project_id)

    # Report
    failed = [r for r in result.module_results if r.status.value == "FAILED"]
    if failed:
        for f in failed:
            print(f"WARNING: Module '{f.module_name}' failed: {f.error_message}", file=sys.stderr)

    print(f"\nPipeline completed in {result.total_elapsed:.1f}s")
    print(f"Output directory: {result.output_directory}")

    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
