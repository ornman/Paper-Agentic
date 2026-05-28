"""Transfer 模块测试

TRANSFER-U01: 路由判定矩阵
TRANSFER-I01: 阶段推进与降级
"""

from __future__ import annotations

import os
import pytest

from app.data_layer.PDF_preprocessor_data.transfer.pipeline import (
    decide_route,
    PipelineStage,
    Route,
    PipelineOrchestrator,
)

_mineru_token = os.environ.get("MINERU_TOKEN", "")
requires_mineru = pytest.mark.skipif(not _mineru_token, reason="需要 MINERU_TOKEN 环境变量")


class TestTransferU01:
    """路由判定矩阵"""

    def test_scan_like_returns_e(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=True,
            has_images=False, has_form_fields=False,
            has_formula_signals=False, has_table_signals=False,
        ) == Route.E

    def test_complex_mixed_returns_d(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=True, has_form_fields=True,
            has_formula_signals=True, has_table_signals=False,
        ) == Route.D

    def test_formula_or_form_or_table_returns_c(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=False, has_form_fields=True,
            has_formula_signals=False, has_table_signals=False,
        ) == Route.C

    def test_formula_signals_returns_c(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=False, has_form_fields=False,
            has_formula_signals=True, has_table_signals=False,
        ) == Route.C

    def test_table_signals_returns_c(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=False, has_form_fields=False,
            has_formula_signals=False, has_table_signals=True,
        ) == Route.C

    def test_images_only_returns_b(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=True, has_form_fields=False,
            has_formula_signals=False, has_table_signals=False,
        ) == Route.B

    def test_plain_text_returns_a(self):
        assert decide_route(
            has_text_layer=True, is_scan_like=False,
            has_images=False, has_form_fields=False,
            has_formula_signals=False, has_table_signals=False,
        ) == Route.A


class TestTransferI01:
    """阶段推进与降级"""

    @requires_mineru
    @pytest.mark.asyncio
    async def test_orchestrator_run_with_real_pdf(self, zh_pdf, tmp_dir):
        """真实 PDF 跑 orchestrator（Route A smoke test）"""
        events = []
        orchestrator = PipelineOrchestrator(
            monitor_callback=lambda e: events.append(e.event)
        )

        state = await orchestrator.run(zh_pdf, output_dir=tmp_dir)

        # 应该有探针事件
        assert "probe.started" in events
        assert "probe.completed" in events

        # 应该有路由决策事件
        assert "routing.decision" in events

        # 状态应有 route
        assert state.route is not None
        assert state.route.value in ("A", "B", "C", "D", "E")

        # 关键：pipeline 必须真正完成（不是 silent fail）
        assert state.stage == PipelineStage.DONE, f"Pipeline 未完成: stage={state.stage}, error={state.error}"

        # 必须产出 chunks
        chunks = getattr(state, "_chunks", [])
        assert len(chunks) > 0, "Pipeline 完成但没有产出 chunks"

        # 必须有 completion 事件
        assert "pipeline.completed" in events

    @requires_mineru
    @pytest.mark.asyncio
    async def test_orchestrator_state_has_probe_result(self, zh_pdf, tmp_dir):
        """验证 probe 结果保存到 state"""
        orchestrator = PipelineOrchestrator()
        state = await orchestrator.run(zh_pdf, output_dir=tmp_dir)

        # probe 结果应该保存到 state
        assert hasattr(state, "_probe_result")
        probe_result = state._probe_result
        assert probe_result.page_count > 0

    @requires_mineru
    @pytest.mark.asyncio
    async def test_orchestrator_route_uses_probe_signals(self, zh_pdf, tmp_dir):
        """验证路由决策使用 probe 的完整信号（不再硬编码）"""
        orchestrator = PipelineOrchestrator()
        state = await orchestrator.run(zh_pdf, output_dir=tmp_dir)

        probe_result = state._probe_result
        # 如果 probe 检测到表格信号，route 应该是 C 或 D
        if probe_result.has_table_signals:
            assert state.route in (Route.C, Route.D)
        elif probe_result.has_formula_signals:
            assert state.route in (Route.C, Route.D)
        elif probe_result.has_images:
            assert state.route in (Route.B, Route.C, Route.D)
