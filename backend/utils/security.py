import hashlib
import secrets

def hash_password(password: str) -> str:
    salt = secrets.token_hex(8)
    h = hashlib.sha256((salt + password).encode()).hexdigest()
    return f"{salt}${h}"

def verify_password(password: str, stored: str) -> bool:
    salt, h = stored.split("$")
    return hashlib.sha256((salt + password).encode()).hexdigest() == h
