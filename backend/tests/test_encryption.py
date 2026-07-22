import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def test_encrypt_decrypt_roundtrip(monkeypatch):
    import config
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config, "ENCRYPTION_KEY", key)

    import importlib
    import core.encryption as encryption
    importlib.reload(encryption)

    ciphertext = encryption.encrypt("ghp_secretvalue123")
    assert ciphertext != "ghp_secretvalue123"
    assert encryption.decrypt(ciphertext) == "ghp_secretvalue123"


def test_encrypt_empty_string_returns_empty(monkeypatch):
    import core.encryption as encryption
    assert encryption.encrypt("") == ""
    assert encryption.decrypt("") == ""


def test_decrypt_invalid_token_returns_empty_string(monkeypatch):
    import config
    from cryptography.fernet import Fernet
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config, "ENCRYPTION_KEY", key)

    import importlib
    import core.encryption as encryption
    importlib.reload(encryption)

    assert encryption.decrypt("not-a-valid-fernet-token") == ""
