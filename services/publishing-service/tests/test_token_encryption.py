import os
import pytest
from unittest.mock import patch
from cryptography.fernet import Fernet, InvalidToken


class TestTokenEncryption:
    """Tests for Fernet token encryption/decryption."""

    def setup_method(self):
        self.test_key = Fernet.generate_key().decode()

    def test_encrypt_then_decrypt_roundtrip(self):
        with patch.dict(os.environ, {"META_TOKEN_ENCRYPTION_KEY": self.test_key}):
            # Re-import to pick up patched env
            from app.services.token_encryption import encrypt_token, decrypt_token
            # Force re-read of settings
            from app.config import Settings
            with patch("app.services.token_encryption.settings", Settings(META_TOKEN_ENCRYPTION_KEY=self.test_key)):
                encrypted = encrypt_token("EAAtest_token_12345")
                assert encrypted != "EAAtest_token_12345"
                decrypted = decrypt_token(encrypted)
                assert decrypted == "EAAtest_token_12345"

    def test_encrypted_token_is_not_plaintext(self):
        with patch.dict(os.environ, {"META_TOKEN_ENCRYPTION_KEY": self.test_key}):
            from app.services.token_encryption import encrypt_token
            from app.config import Settings
            with patch("app.services.token_encryption.settings", Settings(META_TOKEN_ENCRYPTION_KEY=self.test_key)):
                encrypted = encrypt_token("my_secret_token")
                assert "my_secret_token" not in encrypted

    def test_decrypt_with_wrong_key_raises_error(self):
        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()
        from app.services.token_encryption import encrypt_token, decrypt_token
        from app.config import Settings

        with patch("app.services.token_encryption.settings", Settings(META_TOKEN_ENCRYPTION_KEY=key1)):
            encrypted = encrypt_token("token_value")

        with patch("app.services.token_encryption.settings", Settings(META_TOKEN_ENCRYPTION_KEY=key2)):
            with pytest.raises(InvalidToken):
                decrypt_token(encrypted)
