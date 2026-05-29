"""data_layer - 数据层

三层架构：
1. preprocessing - 预处理层
2. indexing + storage - 持久化层
3. retrieval - 检索层
"""

# 预处理层
from .preprocessing.transfer import PipelineOrchestrator, PipelineState, IngestResult
from .preprocessing.mineru_processing import convert_pdf, ConversionResult
from .preprocessing.cleaning import clean_markdown, CleaningResult
from .preprocessing.vlm_understanding import VLMProcessor, VLMResult
from .preprocessing.chunking import semantic_chunk, Chunk, Anchor
from .preprocessing.monitor import PipelineMonitor

# 索引层
from .indexing.embedding import EmbeddingClient
from .indexing.chroma_store import VectorIndex, KeywordIndex, SoftDeleteManager

# 存储层
from .storage.file_management import DirectoryManager
from .storage.monitor import StorageMonitor

# 检索层
from .retrieval.dense import DenseRetriever
from .retrieval.sparse import SparseRetriever
from .retrieval.fusion import rrf_fuse

__all__ = [
    # 预处理层
    "PipelineOrchestrator",
    "PipelineState",
    "IngestResult",
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

    # 索引层
    "EmbeddingClient",
    "VectorIndex",
    "KeywordIndex",
    "SoftDeleteManager",

    # 存储层
    "DirectoryManager",
    "StorageMonitor",

    # 检索层
    "DenseRetriever",
    "SparseRetriever",
    "rrf_fuse",
]
