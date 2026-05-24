"""流水线编排器

负责按序执行各模块（Crawler → DXF_Parser → RAG_Generator → MonteCarlo），
处理超时控制、故障隔离和状态日志输出。
"""

import json
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Optional


class ModuleStatus(Enum):
    """模块执行状态"""
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


@dataclass
class ModuleResult:
    """单个模块的执行结果"""
    module_name: str
    status: ModuleStatus
    output_path: Optional[str] = None
    error_message: Optional[str] = None
    elapsed_seconds: float = 0.0


@dataclass
class PipelineResult:
    """整条流水线的执行结果"""
    project_id: str
    module_results: list[ModuleResult] = field(default_factory=list)
    output_directory: str = ""
    total_elapsed: float = 0.0


class BaseModule(ABC):
    """所有流水线模块的抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """模块名称"""
        ...

    @abstractmethod
    def execute(self, input_data: dict, config: dict) -> dict:
        """执行模块逻辑，返回输出字典"""
        ...

    @abstractmethod
    def validate_input(self, input_data: dict) -> bool:
        """验证输入数据是否合法"""
        ...


class PipelineOrchestrator:
    """流水线编排器，按序执行注册的模块"""

    def __init__(self, config: dict):
        self.config = config
        self.modules: list[BaseModule] = []
        self.results: dict[str, ModuleResult] = {}

    def register_module(self, module: BaseModule) -> None:
        """注册一个模块到流水线"""
        self.modules.append(module)

    def execute(self, project_id: str) -> PipelineResult:
        """按序执行所有注册模块，返回流水线结果。

        故障隔离策略：
        - 单模块异常或超时不会导致Pipeline崩溃
        - 模块失败后，依赖其输出的下游模块被跳过
        - PipelineResult始终被返回，包含所有模块状态
        """
        pipeline_start = time.time()

        # Create output directory structure
        output_base = self.config.get("pipeline", {}).get("output_base", "output")
        today = date.today().isoformat()
        day_dir = Path(output_base) / today
        intermediate_dir = day_dir / "intermediate"
        output_dir = day_dir / "output"
        intermediate_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        pipeline_result = PipelineResult(
            project_id=project_id,
            output_directory=str(output_dir),
        )

        previous_output: dict = {}
        # Track whether an upstream module has failed (sequential dependency)
        upstream_failed = False

        for module in self.modules:
            # Fault isolation: skip downstream modules if upstream failed
            if upstream_failed:
                result = ModuleResult(
                    module_name=module.name,
                    status=ModuleStatus.SKIPPED,
                    error_message="Skipped due to upstream module failure",
                    elapsed_seconds=0.0,
                )
                self._log_status(module.name, ModuleStatus.SKIPPED.value, 0.0)
                self.results[module.name] = result
                pipeline_result.module_results.append(result)
                continue

            module_start = time.time()
            self._log_status(module.name, ModuleStatus.STARTED.value, 0.0)

            try:
                timeout = self.config.get("pipeline", {}).get("module_timeout", 300)
                output = self._run_with_timeout(module, previous_output, timeout=timeout)
                elapsed = time.time() - module_start

                # Save intermediate result
                intermediate_path = intermediate_dir / f"{module.name}_result.json"
                with open(intermediate_path, "w", encoding="utf-8") as f:
                    json.dump(output, f, ensure_ascii=False, indent=2)

                result = ModuleResult(
                    module_name=module.name,
                    status=ModuleStatus.COMPLETED,
                    output_path=str(intermediate_path),
                    elapsed_seconds=elapsed,
                )
                self._log_status(module.name, ModuleStatus.COMPLETED.value, elapsed)
                previous_output = output

            except Exception as e:
                elapsed = time.time() - module_start
                error_type = type(e).__name__
                error_msg = f"{error_type}: {e}"
                result = ModuleResult(
                    module_name=module.name,
                    status=ModuleStatus.FAILED,
                    error_message=error_msg,
                    elapsed_seconds=elapsed,
                )
                self._log_status(module.name, ModuleStatus.FAILED.value, elapsed)
                # Mark upstream as failed so dependents are skipped
                upstream_failed = True

            self.results[module.name] = result
            pipeline_result.module_results.append(result)

        pipeline_result.total_elapsed = time.time() - pipeline_start
        return pipeline_result

    def _run_with_timeout(self, module: BaseModule, input_data: dict, timeout: int = 300) -> dict:
        """带超时控制的模块执行。

        使用ThreadPoolExecutor运行module.execute()，如果超时则抛出TimeoutError。

        Args:
            module: 要执行的模块
            input_data: 输入数据字典
            timeout: 超时秒数，默认300

        Returns:
            模块执行的输出字典

        Raises:
            TimeoutError: 模块执行超过timeout秒
            Exception: 模块执行抛出的任何异常
        """
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(module.execute, input_data, self.config)
            try:
                return future.result(timeout=timeout)
            except FuturesTimeoutError:
                future.cancel()
                raise TimeoutError(
                    f"Module '{module.name}' exceeded timeout of {timeout} seconds"
                )

    def _log_status(self, module_name: str, status: str, elapsed: float) -> None:
        """输出模块状态日志到 stdout"""
        print(f"[{module_name}] {status} (elapsed: {elapsed:.1f}s)")
