"""테스트가 쓰는 키 쌍. 테스트를 돌릴 때마다(프로세스마다) 새로 만든다(저장소에 키가 없다).

EDK_KEY  = EDK 인 척하는 발급자의 키. 공개키가 서버 설정에 들어간다.
OTHER_KEY = 공격자의 키. 서버는 이 키를 모른다.
"""

from collections.abc import MutableMapping

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey


def public_pem(key: RSAPrivateKey) -> str:
    return (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )


EDK_KEY: RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY: RSAPrivateKey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EDK_PUBLIC_PEM: str = public_pem(EDK_KEY)

AUDIENCE = "esg-api-test"
ISSUER = "https://edk.test"
SESSION_SECRET = "test-only-session-secret-0123456789abcdef"


def fill_env(env: MutableMapping[str, str]) -> None:
    """테스트용 설정(config/settings/test_*.py)이 부른다: DB 주소를 뺀 설정 키를 테스트 값으로 채운다."""
    env["EDK_JWT_PUBLIC_KEY"] = EDK_PUBLIC_PEM.replace("\n", "\\n")
    env["EDK_JWT_AUDIENCE"] = AUDIENCE
    env["EDK_JWT_ISSUER"] = ISSUER
    env["SESSION_SECRET"] = SESSION_SECRET
    env["SESSION_TTL_SECONDS"] = "3600"
