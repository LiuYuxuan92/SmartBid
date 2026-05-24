"""流水线集成测试

测试模块注册与按序执行、JSON中间文件传递、
超时控制、故障隔离和状态日志输出。
"""

import json
import tempfile
import time
from pathlib import Path

import pytest

from src.pipeline.orchestrator import (
    BaseModule,
    ModuleResult,
    ModuleStatus,
    PipelineOrchestrator,
    PipelineResult,
)


class MockModuleA(BaseModule):
    """测试用模块A"""

    @property
    def name(self) -> str:
        return "module_a"

    def execute(self, input_data: dict, config: dict) -> dict:
        return {"result": "a_output", "from_input": input_data.get("seed", "none")}

    def validate_input(self, input_data: dict) -> bool:
        return True


class MockModuleB(BaseModule):
    """测试用模块B - 使用前一个模块的输出"""

    @property
    def name(self) -> str:
        return "module_b"

    def execute(self, input_data: dict, config: dict) -> dict:
        return {"result": "b_output", "received": input_data.get("result", "")}

    def validate_input(self, input_data: dict) -> bool:
        return "result" in input_data


class FailingModule(BaseModule):
    """测试用失败模块"""

    @property
    def name(self) -> str:
        return "failing_module"

    def execute(self, input_data: dict, config: dict) -> dict:
        raise RuntimeError("Module execution failed")

    def validate_input(self, input_data: dict) -> bool:
        return True


class TestModuleRegistration:
    """模块注册测试"""

    def test_register_single_module(self):
        orchestrator = PipelineOrchestrator(config={"pipeline": {"output_base": "output"}})
        module = MockModuleA()
        orchestrator.register_module(module)
        assert len(orchestrator.modules) == 1
        assert orchestrator.modules[0].name == "module_a"

    def test_register_multiple_modules(self):
        orchestrator = PipelineOrchestrator(config={"pipeline": {"output_base": "output"}})
        orchestrator.register_module(MockModuleA())
        orchestrator.register_module(MockModuleB())
        assert len(orchestrator.modules) == 2
        assert orchestrator.modules[0].name == "module_a"
        assert orchestrator.modules[1].name == "module_b"

    def test_initial_state_empty(self):
        orchestrator = PipelineOrchestrator(config={})
        assert orchestrator.modules == []
        assert orchestrator.results == {}


class TestSequentialExecution:
    """按序执行测试"""

    def test_single_module_execution(self, tmp_path):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        result = orchestrator.execute("project-001")

        assert result.project_id == "project-001"
        assert len(result.module_results) == 1
        assert result.module_results[0].status == ModuleStatus.COMPLETED
        assert result.module_results[0].module_name == "module_a"
        assert result.total_elapsed > 0

    def test_sequential_data_passing(self, tmp_path):
        """验证前一个模块的输出作为下一个模块的输入"""
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())
        orchestrator.register_module(MockModuleB())

        result = orchestrator.execute("project-002")

        assert len(result.module_results) == 2
        assert result.module_results[0].status == ModuleStatus.COMPLETED
        assert result.module_results[1].status == ModuleStatus.COMPLETED

        # Verify module_b received module_a's output
        intermediate_b = Path(result.module_results[1].output_path)
        with open(intermediate_b, "r", encoding="utf-8") as f:
            b_output = json.load(f)
        assert b_output["received"] == "a_output"

    def test_failed_module_records_error(self, tmp_path):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())

        result = orchestrator.execute("project-003")

        assert len(result.module_results) == 1
        assert result.module_results[0].status == ModuleStatus.FAILED
        assert "Module execution failed" in result.module_results[0].error_message
        assert result.module_results[0].output_path is None


class TestStatusOutput:
    """状态日志输出格式测试"""

    def test_log_status_format(self, tmp_path, capsys):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        orchestrator.execute("project-004")

        captured = capsys.readouterr()
        assert "[module_a] STARTED (elapsed: 0.0s)" in captured.out
        assert "[module_a] COMPLETED (elapsed:" in captured.out

    def test_failed_module_logs_failure(self, tmp_path, capsys):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())

        orchestrator.execute("project-005")

        captured = capsys.readouterr()
        assert "[failing_module] STARTED" in captured.out
        assert "[failing_module] FAILED" in captured.out


class TestOutputDirectoryCreation:
    """输出目录创建测试"""

    def test_creates_intermediate_directory(self, tmp_path):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        orchestrator.execute("project-006")

        from datetime import date
        today = date.today().isoformat()
        intermediate_dir = tmp_path / today / "intermediate"
        assert intermediate_dir.exists()

    def test_creates_output_directory(self, tmp_path):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        result = orchestrator.execute("project-007")

        from datetime import date
        today = date.today().isoformat()
        output_dir = tmp_path / today / "output"
        assert output_dir.exists()
        assert result.output_directory == str(output_dir)

    def test_intermediate_json_file_created(self, tmp_path):
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        result = orchestrator.execute("project-008")

        output_path = Path(result.module_results[0].output_path)
        assert output_path.exists()
        assert output_path.name == "module_a_result.json"

        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["result"] == "a_output"


class SlowModule(BaseModule):
    """测试用超时模块 - 执行时间超过指定超时"""

    def __init__(self, sleep_seconds: float = 2.0):
        self._sleep_seconds = sleep_seconds

    @property
    def name(self) -> str:
        return "slow_module"

    def execute(self, input_data: dict, config: dict) -> dict:
        time.sleep(self._sleep_seconds)
        return {"result": "should_not_reach"}

    def validate_input(self, input_data: dict) -> bool:
        return True


class TestTimeoutControl:
    """超时控制测试"""

    def test_module_exceeding_timeout_gets_terminated(self, tmp_path):
        """模块执行超过timeout应被终止并标记为FAILED"""
        config = {"pipeline": {"output_base": str(tmp_path), "module_timeout": 1}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(SlowModule(sleep_seconds=3.0))

        result = orchestrator.execute("project-timeout")

        assert len(result.module_results) == 1
        assert result.module_results[0].status == ModuleStatus.FAILED
        assert "timeout" in result.module_results[0].error_message.lower()
        assert "exceeded timeout of 1 seconds" in result.module_results[0].error_message

    def test_module_within_timeout_completes(self, tmp_path):
        """模块在timeout内完成应标记为COMPLETED"""
        config = {"pipeline": {"output_base": str(tmp_path), "module_timeout": 5}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(MockModuleA())

        result = orchestrator.execute("project-fast")

        assert result.module_results[0].status == ModuleStatus.COMPLETED


class TestFaultIsolation:
    """故障隔离测试"""

    def test_after_failure_pipeline_returns_result(self, tmp_path):
        """模块失败后Pipeline仍返回PipelineResult"""
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())

        result = orchestrator.execute("project-fault")

        assert isinstance(result, PipelineResult)
        assert result.project_id == "project-fault"
        assert len(result.module_results) == 1
        assert result.module_results[0].status == ModuleStatus.FAILED

    def test_pipeline_never_raises_to_caller(self, tmp_path):
        """Pipeline永远不应向调用者抛出异常"""
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())
        orchestrator.register_module(MockModuleA())

        # This must NOT raise
        result = orchestrator.execute("project-noraise")
        assert isinstance(result, PipelineResult)

    def test_downstream_modules_skipped_on_failure(self, tmp_path):
        """上游模块失败时，下游依赖模块应被跳过"""
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())
        orchestrator.register_module(MockModuleB())

        result = orchestrator.execute("project-skip")

        assert len(result.module_results) == 2
        assert result.module_results[0].status == ModuleStatus.FAILED
        assert result.module_results[1].status == ModuleStatus.SKIPPED
        assert "upstream" in result.module_results[1].error_message.lower()

    def test_timeout_failure_skips_downstream(self, tmp_path):
        """超时导致的失败也应跳过下游模块"""
        config = {"pipeline": {"output_base": str(tmp_path), "module_timeout": 1}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(SlowModule(sleep_seconds=3.0))
        orchestrator.register_module(MockModuleB())

        result = orchestrator.execute("project-timeout-skip")

        assert result.module_results[0].status == ModuleStatus.FAILED
        assert result.module_results[1].status == ModuleStatus.SKIPPED

    def test_error_message_contains_module_info(self, tmp_path):
        """失败时错误信息应包含错误类型"""
        config = {"pipeline": {"output_base": str(tmp_path)}}
        orchestrator = PipelineOrchestrator(config=config)
        orchestrator.register_module(FailingModule())

        result = orchestrator.execute("project-errinfo")

        error_msg = result.module_results[0].error_message
        assert "RuntimeError" in error_msg
        assert "Module execution failed" in error_msg
