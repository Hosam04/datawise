import bcrypt

def _truncate_password(password: str) -> bytes:
    """Truncate password to max 72 bytes safely without splitting a UTF-8 codepoint."""
    password_bytes = password.encode("utf-8")

    if len(password_bytes) <= 72:
        return password_bytes

    truncated = password_bytes[:72]

    # Strip trailing continuation bytes (10xxxxxx).
    while truncated and (truncated[-1] & 0xC0) == 0x80:
        truncated = truncated[:-1]

    # If the cut landed on a multi-byte lead byte (11xxxxxx), strip it too.
    if truncated and (truncated[-1] & 0xC0) == 0xC0:
        truncated = truncated[:-1]

    return truncated

def hash_password(password: str) -> str:
    password_bytes = _truncate_password(password)
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = _truncate_password(plain_password)
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)