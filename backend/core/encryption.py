from cryptography.fernet import Fernet, InvalidToken
from config import ENCRYPTION_KEY
from logs.logger import get_logger

logger = get_logger("encryption")

_fernet = None
if ENCRYPTION_KEY:
    try:
        _fernet = Fernet(ENCRYPTION_KEY.encode())
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid ENCRYPTION_KEY — encryption disabled: {e}")


def encrypt(plaintext: str) -> str:
    """
    User ke GitHub OAuth token ya apna Gemini API key encrypt karke store karo.
    ENCRYPTION_KEY set nahi hai toh crash mat karo — bas warning do (dev-only
    fallback), production mein ye env var zaroor set hona chahiye.
    """
    if not plaintext:
        return ""
    if not _fernet:
        logger.warning("ENCRYPTION_KEY not set — storing value UNENCRYPTED. Set this in production.")
        return plaintext
    return _fernet.encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    """Encrypted value wapas plaintext mein lao. Corrupt/invalid ho toh empty string do."""
    if not ciphertext:
        return ""
    if not _fernet:
        return ciphertext
    try:
        return _fernet.decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("Failed to decrypt value — invalid token or wrong ENCRYPTION_KEY")
        return ""


def generate_key() -> str:
    """One-time helper — run this locally to generate a value for ENCRYPTION_KEY."""
    return Fernet.generate_key().decode()
