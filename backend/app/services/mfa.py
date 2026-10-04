"""MFA TOTP (RFC 6238) — implémentation autonome (hmac/hashlib/base64),
sans dépendance externe. Codes de récupération pour la perte de l'app
authentificatrice ; l'administrateur peut réinitialiser le MFA d'un
compte en cas extrême.
"""
import base64
import hashlib
import hmac
import secrets
import struct
import time
from typing import Optional

# Paramètres standards Google Authenticator
_STEP = 30
_DIGITS = 6
_ISSUER = "OrientSkill AI"


def generate_secret() -> str:
    """Secret base32 de 160 bits, compatible TOTP."""
    raw = secrets.token_bytes(20)
    return base64.b32encode(raw).decode("ascii").rstrip("=")


def totp_at(secret: str, counter: int) -> str:
    key = base64.b32decode(secret + "=" * ((8 - len(secret) % 8) % 8))
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = (struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF) % (10 ** _DIGITS)
    return f"{code:0{_DIGITS}d}"


def verify_totp(secret: str, code: str, window: int = 1) -> bool:
    """Vérifie le code sur la fenêtre [t-window, t+window]."""
    code = (code or "").replace(" ", "").strip()
    if not code.isdigit() or len(code) != _DIGITS:
        return False
    counter = int(time.time()) // _STEP
    return any(hmac.compare_digest(totp_at(secret, counter + delta), code)
               for delta in range(-window, window + 1))


def otpauth_uri(secret: str, account: str) -> str:
    return (
        f"otpauth://totp/{_ISSUER.replace(' ', '%20')}:{account}"
        f"?secret={secret}&issuer={_ISSUER.replace(' ', '%20')}"
        f"&algorithm=SHA1&digits={_DIGITS}&period={_STEP}"
    )


# ------------------------------------------------- codes de récupération

def generate_recovery_codes(n: int = 8) -> list[str]:
    """Codes lisibles « XXXX-XXXX », montrés une seule fois à l'utilisateur."""
    out = []
    for _ in range(n):
        raw = secrets.token_hex(4)  # 8 caractères hexa
        out.append(f"{raw[:4]}-{raw[4:]}".upper())
    return out


def hash_recovery_code(code: str) -> str:
    return hashlib.sha256(code.strip().upper().encode("utf-8")).hexdigest()


def find_recovery_code(hashed_list: list, code: str) -> Optional[str]:
    """Retourne le hachage correspondant si le code est valide."""
    target = hash_recovery_code(code)
    for item in hashed_list:
        if isinstance(item, dict) and item.get("hash") == target and not item.get("used"):
            return target
    return None
