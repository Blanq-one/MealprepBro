"""Password hashing with scrypt (stdlib). The stored form has no `$` (docker compose would read it as a
variable): `scrypt:<n>:<r>:<p>:<salt>:<hash>`, salt and hash base64url without padding."""

import base64
import hashlib
import hmac
import secrets

N, R, P = 2**15, 8, 1
KEY_BYTES = 32
MAX_MEM = 64 * 1024 * 1024  # n=2^15, r=8 needs 32 MiB; the default cap is exactly that, so raise it


class PasswordHashError(ValueError):
    pass


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _derive(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=MAX_MEM, dklen=KEY_BYTES)


def hash_password(password: str, *, n: int = N, r: int = R, p: int = P) -> str:
    if len(password) < 8:
        raise PasswordHashError("use a password of at least 8 characters")
    salt = secrets.token_bytes(16)
    return f"scrypt:{n}:{r}:{p}:{_b64(salt)}:{_b64(_derive(password, salt, n, r, p))}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = encoded.split(":")
        if scheme != "scrypt":
            raise ValueError(scheme)
        expected = _unb64(digest)
        actual = _derive(password, _unb64(salt), int(n), int(r), int(p))
    except (ValueError, TypeError) as exc:
        raise PasswordHashError(
            "AUTH_PASSWORD_HASH isn't a valid hash; make one with `python -m app.cli hash-password`"
        ) from exc
    return hmac.compare_digest(actual, expected)
