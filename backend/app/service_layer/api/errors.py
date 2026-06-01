"""服务层领域异常

仅服务层使用，data_layer 不应依赖此模块。
"""

from __future__ import annotations


class DomainError(Exception):
    def __init__(self, message: str, code: str = "domain_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class ValidationError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="validation_error")


class NotFoundError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="not_found")


class ConflictError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="conflict")


class ServiceUnavailableError(DomainError):
    def __init__(self, message: str):
        super().__init__(message, code="service_unavailable")
