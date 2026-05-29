"""Transfer 模块测试

TRANSFER-I01: 阶段推进与降级
"""

from __future__ import annotations

import os
import pytest

from app.data_layer.preprocessing.transfer.pipeline import (
    PipelineStage,
    PipelineOrchestrator,
)

_mineru_token = os.environ.get("MINERU_TOKEN", "")
requires_mineru = pytest.mark.skipif(not _mineru_token, reason="需要 MINERU_TOKEN 环境变量")


class TestTransferI01:
    """阶段推进与降级"""

    @requires_mineru
    @pytest.mark.asyncio
    async def test_orchestrator_run_with_real_pdf(self, zh_pdf, tmp_dir):
        """真实 PDF 跑 orchestrator smoke test"""
        events = []
        orchestrator = PipelineOrchestrator(
            monitor_callback=lambda e: events.append(e.event)
        )

        state = await orchestrator.run(zh_pdf, output_dir=tmp_dir)

        # 关键：pipeline 必须真正完成（不是 silent fail）
        assert state.stage == PipelineStage.DONE, f"Pipeline 未完成: stage={state.stage}, error={state.error}"

        # 必须产出 chunks
        chunks = getattr(state, "_chunks", [])
        assert len(chunks) > 0, "Pipeline 完成但没有产出 chunks"

        # 必须有 completion 事件
        assert "pipeline.completed" in events
