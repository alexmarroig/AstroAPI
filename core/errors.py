from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4


HTTP_TO_ASTRO_CODE = {
    400: "ASTRO-400",
    401: "ASTRO-401",
    403: "ASTRO-403",
    404: "ASTRO-404",
    409: "ASTRO-409",
    422: "ASTRO-422",
    500: "ASTRO-500",
}


@dataclass(frozen=True)
class AstroError:
    error_id: str
    error_code: str
    message: str
    retryable: bool

    def to_response(self) -> dict:
        return {
            "id": self.error_id,
            "code": self.error_code,
            "message": self.message,
            "retryable": self.retryable,
        }


def build_error(status_code: int, message: str, *, retryable: bool = False) -> AstroError:
    return AstroError(
        error_id=f"err_{uuid4().hex[:12]}",
        error_code=HTTP_TO_ASTRO_CODE.get(status_code, "ASTRO-500"),
        message=message,
        retryable=retryable,
    )

