# 公共错误契约测试
# Task 2 只验证错误模型与模块目录骨架，不涉及 Task 3 之后的业务逻辑。
import copy
import importlib
import pickle


def test_domain_error_exposes_stage_and_message():
    """基础领域错误必须暴露统一字段，供后续模块共享错误契约。"""
    from app.core.errors import DomainError

    err = DomainError(code="retrieval_failed", stage="retrieval", message="boom")

    assert err.code == "retrieval_failed"
    assert err.stage == "retrieval"
    assert err.message == "boom"
    assert err.detail is None


def test_specialized_errors_bind_expected_stage():
    """各子类型错误应绑定稳定的阶段名，避免调用方手写重复字符串。"""
    from app.core.errors import (
        ConfigError,
        IngestionError,
        IndexingError,
        QAError,
        RetrievalError,
        DomainError,
    )

    cases = [
        (ConfigError, "config"),
        (IngestionError, "ingestion"),
        (IndexingError, "indexing"),
        (RetrievalError, "retrieval"),
        (QAError, "qa"),
    ]

    for error_cls, expected_stage in cases:
        err = error_cls(
            code=f"{expected_stage}_failed",
            message="boom",
            detail={"reason": "pytest"},
        )

        assert isinstance(err, DomainError)
        assert err.code == f"{expected_stage}_failed"
        assert err.stage == expected_stage
        assert err.message == "boom"
        assert err.detail == {"reason": "pytest"}


def test_domain_error_and_specialized_errors_support_pickle_and_deepcopy_round_trip():
    """错误对象必须能稳定序列化与深拷贝，否则跨进程、缓存或测试夹具都会崩。"""
    from app.core.errors import DomainError, RetrievalError

    base_error = DomainError(
        code="retrieval_failed",
        stage="retrieval",
        message="boom",
        detail={"reason": "pytest"},
    )
    restored_base_error = pickle.loads(pickle.dumps(base_error))

    assert isinstance(restored_base_error, DomainError)
    assert restored_base_error.code == "retrieval_failed"
    assert restored_base_error.stage == "retrieval"
    assert restored_base_error.message == "boom"
    assert restored_base_error.detail == {"reason": "pytest"}

    specialized_error = RetrievalError(
        code="retrieval_failed",
        message="boom",
        detail={"reason": "pytest"},
    )
    copied_specialized_error = copy.deepcopy(specialized_error)

    assert isinstance(copied_specialized_error, RetrievalError)
    assert copied_specialized_error.code == "retrieval_failed"
    assert copied_specialized_error.stage == "retrieval"
    assert copied_specialized_error.message == "boom"
    assert copied_specialized_error.detail == {"reason": "pytest"}


def test_domain_error_and_specialized_errors_expose_standard_exception_text_contract():
    """错误对象除了业务字段，还必须满足 Python 标准异常文本契约。"""
    from app.core.errors import DomainError, RetrievalError

    base_error = DomainError(
        code="retrieval_failed",
        stage="retrieval",
        message="boom",
    )
    specialized_error = RetrievalError(
        code="retrieval_failed",
        message="boom",
    )

    assert base_error.args == ("boom",)
    assert str(base_error) == "boom"
    assert specialized_error.args == ("boom",)
    assert str(specialized_error) == "boom"

    caught_error = None
    try:
        raise specialized_error
    except RetrievalError as err:
        caught_error = err

    assert caught_error is not None
    assert caught_error.args == ("boom",)
    assert str(caught_error) == "boom"



def test_modules_package_skeleton_is_importable():
    """模块化目录骨架必须可导入，后续任务才能在固定命名空间下继续落代码。"""
    module_names = [
        "app.modules",
        "app.modules.session",
        "app.modules.library",
        "app.modules.ingestion",
        "app.modules.indexing",
        "app.modules.retrieval",
        "app.modules.qa",
    ]

    for module_name in module_names:
        imported_module = importlib.import_module(module_name)
        assert imported_module.__name__ == module_name
