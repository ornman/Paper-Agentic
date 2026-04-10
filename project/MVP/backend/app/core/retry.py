# 自动重试装饰器
# 实现指数退避重试策略：1s → 2s → 4s，最大重试 3 次

from __future__ import annotations

import asyncio
import functools
from typing import Awaitable, Callable, TypeVar

from app.core.errors import IngestionError

T = TypeVar("T")


# 重试配置
MAX_RETRIES = 3
INITIAL_DELAY = 1.0  # 初始延迟 1 秒
BACKOFF_FACTOR = 2.0  # 退避因子


def should_retry(error: Exception) -> bool:
    """判断错误是否应该重试.

    默认策略：所有外部服务调用错误都可重试
    可以根据具体错误类型细化策略

    Args:
        error: 捕获的异常

    Returns:
        是否应该重试
    """
    # 网络相关错误（可重试）
    retryable_errors = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    # API 限流错误（可重试）
    if isinstance(error, IngestionError):
        # 检查错误码
        code = getattr(error, "code", "")
        if code in (
            "api_rate_limit_exceeded",
            "api_timeout",
            "api_connection_error",
        ):
            return True

    return isinstance(error, retryable_errors)


async def async_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_DELAY,
    backoff_factor: float = BACKOFF_FACTOR,
    **kwargs,
) -> T:
    """异步函数重试包装器.

    Args:
        func: 要重试的异步函数
        *args: 函数参数
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        最后一次重试失败的异常
    """
    last_error: Exception | None = None
    delay = initial_delay

    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e

            # 最后一次尝试失败，不再重试
            if attempt >= max_retries:
                break

            # 检查是否应该重试
            if not should_retry(e):
                print(f"⚠️ 不可重试的错误: {e}")
                raise

            # 打印重试信息
            print(
                f"⚠️ {func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
            )
            print(f"⏳ {delay:.1f} 秒后重试...")

            # 等待后重试
            await asyncio.sleep(delay)
            delay *= backoff_factor

    # 所有重试都失败
    raise last_error


def retry_async(
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_DELAY,
    backoff_factor: float = BACKOFF_FACTOR,
) -> Callable:
    """异步函数重试装饰器.

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子

    Returns:
        装饰器函数

    使用示例：
        @retry_async(max_retries=3)
        async def my_function():
            ...
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await async_retry(
                func,
                *args,
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                **kwargs,
            )

        return wrapper

    return decorator


def retry_sync(
    max_retries: int = MAX_RETRIES,
    initial_delay: float = INITIAL_DELAY,
    backoff_factor: float = BACKOFF_FACTOR,
) -> Callable:
    """同步函数重试装饰器.

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        backoff_factor: 退避因子

    Returns:
        装饰器函数

    使用示例：
        @retry_sync(max_retries=3)
        def my_function():
            ...
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            import time

            last_error: Exception | None = None
            delay = initial_delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e

                    # 最后一次尝试失败，不再重试
                    if attempt >= max_retries:
                        break

                    # 检查是否应该重试
                    if not should_retry(e):
                        print(f"⚠️ 不可重试的错误: {e}")
                        raise

                    # 打印重试信息
                    print(
                        f"⚠️ {func.__name__} 失败 (尝试 {attempt + 1}/{max_retries + 1}): {e}"
                    )
                    print(f"⏳ {delay:.1f} 秒后重试...")

                    # 等待后重试
                    time.sleep(delay)
                    delay *= backoff_factor

            # 所有重试都失败
            raise last_error

        return wrapper

    return decorator
