import secrets
secret_key = secrets.token_hex(32)  # 32 bytes (256-bit key)
print(secret_key)
