# 公共领域错误定义
# 这里先建立最小统一错误契约，后续各模块都基于这些类型传播错误信息。
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _restore_domain_error(
    error_cls: type[DomainError],
    code: str,
    stage: str,
    message: str,
    detail: Any,
) -> DomainError:
    """恢复 pickle / deepcopy 期间的错误对象。

    本质原因：
    - BaseException 默认会依赖 `args` 重建实例。
    - 但这里的 dataclass 字段和子类构造签名并不等同于 `args`。
    - 一旦直接走默认重建路径，就会把参数个数和语义对错位，最终在 pickle
      round-trip 或 deepcopy 时触发 `TypeError`。

    这里显式提供统一恢复入口，让基类和各个特化错误都走稳定的重建逻辑。
    """

    if error_cls is DomainError:
        return error_cls(code=code, stage=stage, message=message, detail=detail)

    return error_cls(code=code, message=message, detail=detail)


@dataclass(slots=True)
class DomainError(Exception):
    """领域层统一错误基类。

    设计目的：
    1. 统一所有业务错误暴露的字段结构，避免各模块自行拼装错误对象。
    2. 让上层路由、服务、日志系统可以稳定读取 code/stage/message/detail。
    3. 先保持最小能力，只做结构统一，不提前引入 HTTP 语义或复杂序列化逻辑。
    """

    code: str
    stage: str
    message: str
    detail: Any = field(default=None)

    def __post_init__(self) -> None:
        """补齐标准 Exception 基类状态。

        dataclass 自动生成的 `__init__` 只会给字段赋值，不会自动调用
        `Exception.__init__()`。结果就是：
        - `args` 会保持空元组
        - `str(err)` 会变成空字符串
        - `raise err` 后，标准异常文本接口仍然是空的

        这里显式把 `message` 同步给基类，确保领域错误既保留业务字段，
        也满足 Python 异常对象的通用行为契约。

        注意：这里直接调用 `Exception.__init__()`，而不是零参数 `super()`。
        在当前 `dataclass(slots=True)` + 异常继承结构下，显式调用基类更稳定，
        可以避免运行时对 `super()` 解析失败。
        """

        Exception.__init__(self, self.message)

    def __reduce__(self) -> tuple[Any, tuple[type[DomainError], str, str, str, Any]]:
        """为 pickle 和 deepcopy 提供稳定的重建协议。

        不能依赖 BaseException 默认的 `args` 机制，原因是：
        - `DomainError` 需要 `code/stage/message/detail` 四段业务字段。
        - 特化错误只暴露 `code/message/detail` 三段构造参数，`stage` 在子类内部固定。
        - 如果继续让运行时只拿 `Exception.args == (message,)` 去重建，反序列化时必然丢字段。

        因此这里显式返回完整业务状态，再由 `_restore_domain_error()` 按类型恢复。
        """

        return (
            _restore_domain_error,
            (type(self), self.code, self.stage, self.message, self.detail),
        )

    def __reduce_ex__(
        self,
        protocol: int,
    ) -> tuple[Any, tuple[type[DomainError], str, str, str, Any]]:
        """兼容 pickle 与 copy 模块优先调用的扩展重建入口。"""

        del protocol
        return self.__reduce__()


class ConfigError(DomainError):
    """配置阶段错误。"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(code=code, stage="config", message=message, detail=detail)


class IngestionError(DomainError):
    """导入阶段错误。"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(code=code, stage="ingestion", message=message, detail=detail)


class IndexingError(DomainError):
    """索引阶段错误。"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(code=code, stage="indexing", message=message, detail=detail)


class RetrievalError(DomainError):
    """检索阶段错误。"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(code=code, stage="retrieval", message=message, detail=detail)


class QAError(DomainError):
    """问答阶段错误。"""

    def __init__(self, code: str, message: str, detail: Any = None) -> None:
        super().__init__(code=code, stage="qa", message=message, detail=detail)
