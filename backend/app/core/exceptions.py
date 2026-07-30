"""自定义异常类"""


class LogosError(Exception):
    """基础异常"""

    def __init__(self, code: str, message: str, status: int = 500, details: dict | None = None):
        self.code = code
        self.message = message
        self.status = status
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self):
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "status": self.status,
                "details": self.details,
            }
        }


class EntityNotFoundError(LogosError):
    """实体未找到"""

    def __init__(self, entity_id: str):
        super().__init__(
            code="not_found",
            message=f"未找到名词'{entity_id}'",
            status=404,
        )


class ExternalServiceError(LogosError):
    """外部服务错误"""

    def __init__(self, service: str, detail: str = ""):
        super().__init__(
            code="external_service_error",
            message=f"外部服务'{service}'请求失败",
            status=502,
            details={"service": service, "detail": detail},
        )
