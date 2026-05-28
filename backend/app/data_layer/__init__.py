"""data_layer - 数据层

三层架构：
1. PDF_preprocessor_data - 预处理层
2. data_persistence - 持久化层
3. retrieval - 检索层
"""

# 预处理层
from .PDF_preprocessor_data.probe import probe_pdf, ProbeResult
from .PDF_preprocessor_data.transfer import PipelineOrchestrator, PipelineState, Route
from .PDF_preprocessor_data.transformation import convert_pdf, ConversionResult
from .PDF_preprocessor_data.cleaning import clean_markdown, CleaningResult
from .PDF_preprocessor_data.vlm_understanding import VLMProcessor, VLMResult
from .PDF_preprocessor_data.chunking import semantic_chunk, Chunk, Anchor
from .PDF_preprocessor_data.monitor import PipelineMonitor

# 持久化层
from .data_persistence.embedding import EmbeddingClient
from .data_persistence.config import DataLayerConfig, load_config
from .data_persistence.chroma_store import VectorIndex, KeywordIndex, SoftDeleteManager
from .data_persistence.file_management import DirectoryManager
from .data_persistence.document_service import DocumentIngestService, IngestResult
from .data_persistence.monitor import StorageMonitor

# 检索层
from .retrieval.dense import DenseRetriever
from .retrieval.sparse import SparseRetriever
from .retrieval.fusion import rrf_fuse

__all__ = [
    # 预处理层
    "probe_pdf",
    "ProbeResult",
    "PipelineOrchestrator",
    "PipelineState",
    "Route",
    "convert_pdf",
    "ConversionResult",
    "clean_markdown",
    "CleaningResult",
    "VLMProcessor",
    "VLMResult",
    "semantic_chunk",
    "Chunk",
    "Anchor",
    "PipelineMonitor",

    # 持久化层
    "EmbeddingClient",
    "DataLayerConfig",
    "load_config",
    "VectorIndex",
    "KeywordIndex",
    "SoftDeleteManager",
    "DirectoryManager",
    "DocumentIngestService",
    "IngestResult",
    "StorageMonitor",

    # 检索层
    "DenseRetriever",
    "SparseRetriever",
    "rrf_fuse",
]
