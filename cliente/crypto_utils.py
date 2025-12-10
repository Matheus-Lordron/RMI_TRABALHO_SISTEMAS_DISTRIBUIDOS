import bcrypt

# Gera um hash seguro em formato STRING (utf-8)
def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    return hashed.decode()  # transforma bytes -> string

# Verifica senha a partir de hash em STRING
def verify_password(password: str, hashed_str: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed_str.encode())
