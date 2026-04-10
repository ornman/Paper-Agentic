# 错误信息与解决方案映射
# 为每种错误类型提供用户友好的错误信息和解决建议

from __future__ import annotations

from typing import Any

# 错误信息映射表
_ERROR_MESSAGES: dict[str, dict[str, str]] = {
    # 配置错误
    "missing_api_key": {
        "user_message": "API Key 未配置",
        "suggestion": "请在 .env 文件中配置相应的 API Key（KIMI_API_KEY、SILICONFLOW_API_KEY、DEEPSEEK_API_KEY）",
        "severity": "critical",
    },
    "invalid_api_key": {
        "user_message": "API Key 无效",
        "suggestion": "请检查 .env 文件中的 API Key 是否正确，或联系 API 提供商重新生成",
        "severity": "critical",
    },

    # 网络错误
    "connection_error": {
        "user_message": "无法连接到 API 服务",
        "suggestion": "请检查网络连接，确认 API 服务地址是否正确。如果问题持续，可能是服务暂时不可用",
        "severity": "warning",
    },
    "timeout_error": {
        "user_message": "API 请求超时",
        "suggestion": "API 服务响应时间过长。可以尝试：1) 稍后重试，2) 检查网络状况，3) 联系技术支持",
        "severity": "warning",
    },
    "rate_limit_exceeded": {
        "user_message": "API 调用次数超限",
        "suggestion": "API 调用频率过高，请稍后重试。如需更高配额，请联系 API 提供商升级套餐",
        "severity": "warning",
    },

    # 导入错误
    "file_not_found": {
        "user_message": "文件不存在",
        "suggestion": "请确认文件路径是否正确，文件是否存在。支持上传的文件类型：PDF",
        "severity": "error",
    },
    "invalid_file_format": {
        "user_message": "文件格式不支持",
        "suggestion": "当前仅支持 PDF 格式文件。请上传正确的文件格式",
        "severity": "error",
    },
    "mineru_parse_failed": {
        "user_message": "PDF 解析失败",
        "suggestion": "PDF 文件可能损坏或格式不支持。请尝试：1) 重新下载 PDF，2) 使用其他 PDF 转换工具，3) 联系技术支持",
        "severity": "error",
    },
    "cleaned_document_empty": {
        "user_message": "PDF 清洗后无有效内容",
        "suggestion": "PDF 可能是扫描版图片或无法提取文本。请尝试：1) 使用包含可提取文本的 PDF，2) 联系技术支持",
        "severity": "warning",
    },

    # 索引错误
    "embedding_failed": {
        "user_message": "向量化处理失败",
        "suggestion": "文本向量化过程中出现错误。系统将自动重试，如果问题持续，请联系技术支持",
        "severity": "error",
    },
    "qdrant_storage_failed": {
        "user_message": "向量库存储失败",
        "suggestion": "向量数据存储时出现错误。请检查磁盘空间，或联系技术支持",
        "severity": "error",
    },

    # 检索错误
    "no_relevant_results": {
        "user_message": "未找到相关内容",
        "suggestion": "当前文献库中没有与您问题相关的内容。请尝试：1) 添加更多相关文献，2) 改写问题关键词",
        "severity": "info",
    },
    "retrieval_failed": {
        "user_message": "检索过程失败",
        "suggestion": "文献检索时出现错误。系统将自动重试，如果问题持续，请联系技术支持",
        "severity": "error",
    },

    # 问答错误
    "llm_generation_failed": {
        "user_message": "AI 回答生成失败",
        "suggestion": "AI 模型生成回答时出现错误。系统将自动重试，如果问题持续，可能是因为：1) API 余额不足，2) 网络不稳定",
        "severity": "error",
    },

    # 通用错误
    "internal_error": {
        "user_message": "系统内部错误",
        "suggestion": "系统遇到意外错误。请尝试：1) 刷新页面重试，2) 检查网络连接，3) 联系技术支持",
        "severity": "critical",
    },
    "unknown_error": {
        "user_message": "未知错误",
        "suggestion": "系统遇到无法识别的错误。请联系技术支持并提供错误详情",
        "severity": "critical",
    },
}


def get_error_message(error_code: str) -> dict[str, str] | None:
    """获取错误代码对应的用户友好信息.

    Args:
        error_code: 错误代码

    Returns:
        错误信息字典，如果未找到则返回 None
    """
    return _ERROR_MESSAGES.get(error_code)


def format_user_error(
    error_code: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """格式化用户友好的错误响应.

    Args:
        error_code: 错误代码
        context: 额外的上下文信息

    Returns:
        格式化的错误响应
    """
    error_info = get_error_message(error_code)
    if error_info is None:
        error_info = _ERROR_MESSAGES["unknown_error"]

    result = {
        "code": error_code,
        "user_message": error_info["user_message"],
        "suggestion": error_info["suggestion"],
        "severity": error_info["severity"],
    }

    if context:
        result["context"] = context

    return result


def get_http_status_code(severity: str) -> int:
    """根据错误严重程度获取 HTTP 状态码.

    Args:
        severity: 错误严重程度（critical/error/warning/info）

    Returns:
        HTTP 状态码
    """
    severity_to_status = {
        "critical": 500,
        "error": 400,
        "warning": 200,  # 警告级别仍然返回成功，但在数据中标注警告
        "info": 200,
    }
    return severity_to_status.get(severity, 500)
