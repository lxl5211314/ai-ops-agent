from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

VALIDATION = "VALIDATION"
NOT_FOUND = "NOT_FOUND"
CONFLICT = "CONFLICT"
UNPROCESSABLE = "UNPROCESSABLE"
LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
INTERNAL = "INTERNAL"

_STATUS_BY_CODE = {
    VALIDATION: 400,
    NOT_FOUND: 404,
    CONFLICT: 409,
    UNPROCESSABLE: 422,
    LLM_UNAVAILABLE: 503,
    INTERNAL: 500,
}


class AppError(Exception):
    def __init__(self, code: str, message: str, detail=None):
        self.code = code
        self.message = message
        self.detail = detail
        super().__init__(message)


def error_body(code: str, message: str, detail=None) -> dict:
    return {"error": {"code": code, "message": message, "detail": detail}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError):
        return JSONResponse(
            status_code=_STATUS_BY_CODE.get(exc.code, 500),
            content=error_body(exc.code, exc.message, exc.detail),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content=error_body(VALIDATION, "请求参数不合法", exc.errors()),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=error_body(INTERNAL, "服务内部错误，请稍后重试", None),
        )
