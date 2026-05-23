"""MinerU API 客户端.

用于远程解析 PDF 文档，返回结构化 JSON 和图片文件。
"""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.core.config import get_settings

settings = get_settings()

_API_BASE = settings.mineru_base_url


class MinerUTask:
    """MinerU 解析任务."""

    def __init__(self, task_id: str, base_url: str = _API_BASE):
        self.task_id = task_id
        self.base_url = base_url
        self.status_url = f"{base_url}/tasks/{task_id}"
        self.result_url = f"{base_url}/tasks/{task_id}/result"

    def poll(self) -> dict:
        """轮询任务状态，直到完成或超时."""
        start = time.time()
        timeout = settings.mineru_timeout
        interval = settings.mineru_poll_interval

        while True:
            if time.time() - start > timeout:
                raise TimeoutError(f"MinerU task {self.task_id} timeout after {timeout}s")

            resp = httpx.get(self.status_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            status = data.get("status")
            if status == "completed":
                return data
            elif status == "failed":
                error = data.get("error", "Unknown error")
                raise RuntimeError(f"MinerU task failed: {error}")
            elif status in ("pending", "processing"):
                time.sleep(interval)
            else:
                raise RuntimeError(f"Unknown task status: {status}")


class MinerUClient:
    """MinerU API 客户端."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ):
        self.api_key = api_key or settings.mineru_api_key
        self.base_url = base_url or settings.mineru_base_url
        self.submit_url = f"{self.base_url}/submit"
        self._headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def submit_pdf(
        self,
        pdf_path: Path,
        parse_images: bool = True,
        parse_tables: bool = True,
    ) -> MinerUTask:
        """提交 PDF 解析任务.

        Args:
            pdf_path: PDF 文件路径
            parse_images: 是否解析图片
            parse_tables: 是否解析表格

        Returns:
            MinerUTask 实例
        """
        # 检查文件是否存在
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        # 读取文件
        pdf_bytes = pdf_path.read_bytes()

        # 提交任务
        files = {
            "file": (pdf_path.name, pdf_bytes, "application/pdf"),
        }
        data = {
            "parse_images": str(parse_images).lower(),
            "parse_tables": str(parse_tables).lower(),
        }

        resp = httpx.post(
            self.submit_url,
            files=files,
            data=data,
            headers={"Authorization": self._headers["Authorization"]},
            timeout=120,
        )
        resp.raise_for_status()
        result = resp.json()

        task_id = result.get("task_id")
        if not task_id:
            raise ValueError(f"Invalid response: {result}")

        return MinerUTask(task_id, self.base_url)

    def parse_pdf(
        self,
        pdf_path: Path,
        output_dir: Path | None = None,
        parse_images: bool = True,
        parse_tables: bool = True,
    ) -> Path:
        """解析 PDF 并下载结果.

        Args:
            pdf_path: PDF 文件路径
            output_dir: 输出目录（默认与 PDF 同目录）
            parse_images: 是否解析图片
            parse_tables: 是否解析表格

        Returns:
            输出目录路径（包含 content_list_v2.json 和 images/）
        """
        # 提交任务
        task = self.submit_pdf(pdf_path, parse_images, parse_tables)

        # 等待完成
        result = task.poll()

        # 确定输出目录
        if output_dir is None:
            output_dir = pdf_path.parent / f"{pdf_path.name}-extracted"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 下载结果
        download_url = result.get("download_url")
        if not download_url:
            raise ValueError(f"No download URL in response: {result}")

        resp = httpx.get(download_url, timeout=120)
        resp.raise_for_status()

        # 解压到输出目录
        import zipfile
        import io

        with zipfile.ZipFile(io.BytesIO(resp.content)) as zip_ref:
            zip_ref.extractall(output_dir)

        return output_dir


# 便捷函数
def parse_pdf(
    pdf_path: Path | str,
    output_dir: Path | str | None = None,
    api_key: str | None = None,
) -> Path:
    """便捷函数：解析 PDF 文件.

    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录（可选）
        api_key: MinerU API Key（可选，默认使用配置）

    Returns:
        输出目录路径
    """
    pdf_path = Path(pdf_path) if isinstance(pdf_path, str) else pdf_path
    if output_dir:
        output_dir = Path(output_dir) if isinstance(output_dir, str) else output_dir

    client = MinerUClient(api_key=api_key)
    return client.parse_pdf(pdf_path, output_dir)
