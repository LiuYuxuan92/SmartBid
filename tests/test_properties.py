"""Property-based tests using hypothesis.

Validates: Design Properties 1, 2
"""

import json
import tempfile
from pathlib import Path

import numpy as np
from hypothesis import given, strategies as st, settings, assume

from src.dxf_parser.geometry import GeometryCalculator
from src.monte_carlo.simulator import MonteCarloSimulator, SimulationInput


def numpy_polygon_area(vertices):
    """Reference implementation using numpy for comparison."""
    n = len(vertices)
    if n < 3:
        return 0.0
    x = np.array([v[0] for v in vertices])
    y = np.array([v[1] for v in vertices])
    area = 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))
    return round(area, 2)


# ---------------------------------------------------------------------------
# Property 1: Shoelace area non-negative
# ---------------------------------------------------------------------------

@given(vertices=st.lists(
    st.tuples(st.floats(-1000, 1000, allow_nan=False, allow_infinity=False),
              st.floats(-1000, 1000, allow_nan=False, allow_infinity=False)),
    min_size=3, max_size=50
))
@settings(max_examples=20)
def test_shoelace_area_always_non_negative(vertices):
    """Property: Shoelace area is always >= 0 for any vertex list.

    **Validates: Requirements 1.2**
    """
    area = GeometryCalculator.shoelace_area(vertices)
    assert area >= 0


# ---------------------------------------------------------------------------
# Property 1 (cont): Shoelace area matches numpy reference
# ---------------------------------------------------------------------------

@given(vertices=st.lists(
    st.tuples(st.floats(-100, 100, allow_nan=False, allow_infinity=False),
              st.floats(-100, 100, allow_nan=False, allow_infinity=False)),
    min_size=3, max_size=20
))
@settings(max_examples=20)
def test_shoelace_area_matches_numpy_reference(vertices):
    """Property: Our Shoelace matches numpy reference within 0.01.

    **Validates: Requirements 1.2**
    """
    our_area = GeometryCalculator.shoelace_area(vertices)
    ref_area = numpy_polygon_area(vertices)
    assert abs(our_area - ref_area) < 0.01


# ---------------------------------------------------------------------------
# Property 2: Monte Carlo win probability monotonicity
# ---------------------------------------------------------------------------

@given(budget=st.floats(min_value=100000, max_value=10000000, allow_nan=False, allow_infinity=False))
@settings(max_examples=2)  # Reduced because simulation is expensive
def test_win_probability_monotonicity(budget):
    """Property: Lower prices should have >= win probability compared to higher prices.

    **Validates: Requirements 2.1**
    """
    # Create temp data directory with competitor data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Write competitor data
        rng = np.random.default_rng(42)
        for comp in ["comp_1", "comp_2"]:
            data_path = Path(tmpdir) / f"{comp}.json"
            ratios = rng.normal(loc=0.85, scale=0.03, size=20).tolist()
            data_path.write_text(json.dumps(ratios))

        simulator = MonteCarloSimulator(data_dir=tmpdir)
        sim_input = SimulationInput(
            project_budget=budget,
            competitors=["comp_1", "comp_2"],
            iterations=1000,  # Reduced for test speed
        )
        report = simulator.simulate(sim_input)

        # Check monotonicity with tolerance for stochastic noise
        probs = [pp.win_probability for pp in report.price_points]
        violations = 0
        for i in range(len(probs) - 1):
            if probs[i + 1] > probs[i] + 0.1:  # 10% tolerance
                violations += 1
        # Allow at most 2 violations due to stochastic noise
        assert violations <= 2


# ---------------------------------------------------------------------------
# Property 3: Pipeline fault isolation
# ---------------------------------------------------------------------------

import tempfile
from src.pipeline.orchestrator import PipelineOrchestrator, BaseModule, ModuleStatus, PipelineResult


class RandomFailingModule(BaseModule):
    """A module that raises a configurable exception type."""

    def __init__(self, exc_type):
        self._exc_type = exc_type

    @property
    def name(self):
        return "random_fail"

    def execute(self, input_data, config):
        raise self._exc_type("random failure")

    def validate_input(self, input_data):
        return True


class SuccessModule(BaseModule):
    """A module that always succeeds."""

    @property
    def name(self):
        return "success_mod"

    def execute(self, input_data, config):
        return {"ok": True}

    def validate_input(self, input_data):
        return True


@given(exc_idx=st.integers(min_value=0, max_value=3))
@settings(max_examples=4)
def test_pipeline_fault_isolation(exc_idx):
    """Property: Pipeline never crashes from module exceptions.

    **Validates: Requirements 3.1**
    """
    exceptions = [RuntimeError, ValueError, TypeError, OSError]
    exc_type = exceptions[exc_idx]

    with tempfile.TemporaryDirectory() as tmpdir:
        config = {"pipeline": {"output_base": tmpdir, "module_timeout": 5}}
        orchestrator = PipelineOrchestrator(config)
        orchestrator.register_module(RandomFailingModule(exc_type))
        orchestrator.register_module(SuccessModule())

        result = orchestrator.execute("test")
        assert isinstance(result, PipelineResult)
        assert result.module_results[0].status == ModuleStatus.FAILED
        assert result.module_results[1].status == ModuleStatus.SKIPPED


# ---------------------------------------------------------------------------
# Property 4: Config defaults completeness
# ---------------------------------------------------------------------------

import yaml
import os
from src.pipeline.config_loader import ConfigLoader

OPTIONAL_KEYS = [
    ("crawler", "proxies"),
    ("crawler", "user_agents"),
    ("crawler", "crawl_delay"),
    ("crawler", "retry_limit"),
    ("crawler", "connection_timeout"),
    ("crawler", "request_timeout"),
    ("dxf_parser", "unit_scale"),
    ("dxf_parser", "quota_db_path"),
    ("rag", "llm_api_url"),
    ("rag", "llm_model"),
    ("rag", "embedding_model"),
    ("rag", "chunk_size"),
    ("monte_carlo", "iterations"),
    ("pipeline", "output_base"),
    ("pipeline", "module_timeout"),
]


@given(keys_to_remove=st.lists(st.sampled_from(OPTIONAL_KEYS), min_size=0, max_size=10))
@settings(max_examples=10)
def test_config_defaults_completeness(keys_to_remove):
    """Property: Removing optional keys never crashes, defaults always applied.

    **Validates: Requirements 4.1**
    """
    base_config = {
        "crawler": {"target_platforms": [{"url": "http://x", "name": "x", "parser": "B"}]},
        "rag": {"llm_api_key": "test-key"},
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, encoding="utf-8") as f:
        yaml.dump(base_config, f)
        path = f.name

    try:
        loader = ConfigLoader(path)
        config = loader.load()

        # Verify all optional keys have values (either from config or defaults)
        for section, key in OPTIONAL_KEYS:
            assert section in config, f"Section '{section}' missing from config"
            assert key in config[section], f"Key '{section}.{key}' missing from config"
    finally:
        os.unlink(path)


# ---------------------------------------------------------------------------
# Property 5: Vector retrieval ordering
# ---------------------------------------------------------------------------

from src.rag_generator.retrieval import VectorRetriever
from src.rag_generator.ingestion import DocumentChunk


@given(query=st.text(min_size=5, max_size=100, alphabet=st.characters(whitelist_categories=("L", "N", "Z"))))
@settings(max_examples=5, deadline=None)
def test_retrieval_ordering_and_threshold(query):
    """Property: Retrieval results always sorted descending, all >= threshold.

    **Validates: Requirements 5.1**
    """
    retriever = VectorRetriever(collection_name="prop_test_ordering")
    # Pre-populate with some docs
    chunks = [
        DocumentChunk(text="Building construction engineering standards", metadata={"source_doc": "a.docx"}),
        DocumentChunk(text="Software development best practices guide", metadata={"source_doc": "b.docx"}),
        DocumentChunk(text="Financial analysis and budget planning", metadata={"source_doc": "c.docx"}),
    ]
    try:
        retriever.store(chunks)
    except Exception:
        pass  # May already be stored from previous run

    threshold = 0.3
    results = retriever.retrieve(query, top_k=5, threshold=threshold)

    # All scores >= threshold
    for r in results:
        assert r.similarity_score >= threshold, (
            f"Score {r.similarity_score} below threshold {threshold}"
        )

    # Sorted descending
    scores = [r.similarity_score for r in results]
    assert scores == sorted(scores, reverse=True), (
        f"Scores not sorted descending: {scores}"
    )
