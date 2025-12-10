# server/crypto_utils.py
import bcrypt

# 🔒 Gera hash a partir de senha em texto
def hash_password(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())

# 🔓 Verifica se senha em texto corresponde ao hash
def verify_password(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode(), hashed)
