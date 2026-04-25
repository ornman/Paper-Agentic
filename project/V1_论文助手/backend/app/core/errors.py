from fastapi import HTTPException


class AppError(HTTPException):
    def __init__(self, code: int, message: str):
        self.app_code = code
        super().__init__(status_code=400, detail={"code": code, "message": message})


# 客户端错误 1000-1999
class ParamError(AppError):
    def __init__(self, message: str):
        super().__init__(code=1001, message=message)


# 业务错误 2000-2999
class PaperNotFoundError(AppError):
    def __init__(self, paper_id: str):
        super().__init__(code=2001, message=f"论文不存在: {paper_id}")


class PaperExistsError(AppError):
    def __init__(self, file_hash: str):
        super().__init__(code=2002, message="该论文已导入")


class ImportFailedError(AppError):
    def __init__(self, message: str, stage: str | None = None):
        self.stage = stage
        super().__init__(code=2003, message=message)


# 外部服务错误 3000-3999
class ExternalServiceError(AppError):
    def __init__(self, code: int, message: str):
        super().__init__(code=code, message=message)
