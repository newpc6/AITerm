import os
from cryptography.fernet import Fernet


class CryptoService:
    _instance = None

    def __init__(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.key_path = os.path.join(os.path.dirname(base), "data", "secret.key")
        if os.path.exists(self.key_path):
            with open(self.key_path, "rb") as f:
                self.key = f.read()
        else:
            self.key = Fernet.generate_key()
            os.makedirs(os.path.dirname(self.key_path), exist_ok=True)
            with open(self.key_path, "wb") as f:
                f.write(self.key)
        self.cipher = Fernet(self.key)

    def encrypt(self, plain: str) -> str:
        return self.cipher.encrypt(plain.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        return self.cipher.decrypt(encrypted.encode()).decode()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
