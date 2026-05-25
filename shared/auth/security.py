import base64
import hashlib
import hmac
import os
import secrets

try:
    import bcrypt
except Exception:  # pragma: no cover - optional until requirements are installed
    bcrypt = None


TOKEN_BYTES = 32


def generate_token() -> str:
    """Generate a random 256-bit token suitable for persistent login."""
    return secrets.token_urlsafe(TOKEN_BYTES)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password vuota")
    if bcrypt is not None:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 240000)
    return "pbkdf2_sha256$240000$%s$%s" % (
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"),
    )


def verify_password(password: str, stored: str) -> bool:
    if not password or not stored:
        return False
    stored = str(stored)
    if stored.startswith("$2") and bcrypt is not None:
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored.encode("utf-8"))
        except Exception:
            return False
    if stored.startswith("pbkdf2_sha256$"):
        try:
            _, rounds, salt_b64, digest_b64 = stored.split("$", 3)
            salt = base64.b64decode(salt_b64)
            expected = base64.b64decode(digest_b64)
            actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
            return hmac.compare_digest(actual, expected)
        except Exception:
            return False

    # Legacy compatibility: existing Superba records may still contain plaintext.
    # Successful legacy login is upgraded immediately by users.update_user_password().
    return hmac.compare_digest(password, stored)


def password_needs_upgrade(stored: str) -> bool:
    stored = str(stored or "")
    if bcrypt is not None:
        return not stored.startswith("$2")
    return not stored.startswith("pbkdf2_sha256$")
