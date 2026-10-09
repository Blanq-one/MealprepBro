"""An error that carries its own application/problem+json response (rendered by app/api/errors.py)."""


class ProblemError(Exception):
    def __init__(self, status: int, title: str, detail: str, headers: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.status, self.title, self.detail, self.headers = status, title, detail, headers or {}
