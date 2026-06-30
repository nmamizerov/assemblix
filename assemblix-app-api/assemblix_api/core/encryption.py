from cryptography.fernet import Fernet


class EncryptionService:
    """Symmetric encryption using Fernet (AES-128 in CBC mode)."""

    def __init__(self, encryption_key: str):
        if not encryption_key:
            raise ValueError("Encryption key не может быть пустым")

        self._fernet = Fernet(encryption_key.encode())

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return plaintext

        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """Raises cryptography.fernet.InvalidToken if the data is corrupt or the key is wrong."""
        if not ciphertext:
            return ciphertext

        decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
        return decrypted_bytes.decode()

    @staticmethod
    def generate_key() -> str:
        key_bytes = Fernet.generate_key()
        return key_bytes.decode()


_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    global _encryption_service

    if _encryption_service is None:
        raise RuntimeError(
            "EncryptionService не инициализирован. "
            "Вызовите init_encryption_service() при запуске приложения."
        )

    return _encryption_service


def init_encryption_service(encryption_key: str) -> None:
    global _encryption_service
    _encryption_service = EncryptionService(encryption_key)
