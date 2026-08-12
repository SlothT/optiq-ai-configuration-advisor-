from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class EncryptionError(RuntimeError):
    pass


def _get_fernet() -> Fernet:
    if not settings.fernet_key:
        raise EncryptionError("FERNET_KEY is required for encrypted provider storage")
    return Fernet(settings.fernet_key.encode("utf-8"))


def encrypt_text(value: str) -> str:
    token = _get_fernet().encrypt(value.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_text(value: str) -> str:
    try:
        decrypted = _get_fernet().decrypt(value.encode("utf-8"))
        return decrypted.decode("utf-8")
    except InvalidToken as exc:
        raise EncryptionError("Unable to decrypt provider secret") from exc
