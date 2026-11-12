"""로컬에서 EDK 인 척하는 도구. 진짜 EDK 가 없으므로, 키 쌍을 만들고 그 키로 토큰을 서명한다.

    uv run python scripts/dev_edk.py public-key     # 키 쌍이 없으면 만들고, 공개키를 한 줄로 낸다(.env 에 넣을 꼴)
    uv run python scripts/dev_edk.py token --tenant tenant-a --sub user-1 --role editor --name 김담당

키 쌍은 apps/api-py/.dev-keys/ 에 생긴다(git 밖). 이 컴퓨터에서만 쓰는 연습용이고 진짜 EDK 의 키가 아니다.
개인키는 「발급자」만 갖는 것이다: 서버(api-py 컨테이너)에는 공개키만 준다.
"""

import argparse
import os
import time
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey

KEY_DIR = Path(__file__).resolve().parent.parent / ".dev-keys"
PRIVATE_KEY_FILE = KEY_DIR / "edk-private.pem"
# compose.yaml 의 기본값과 같다. .env 에서 바꿨으면 같은 이름의 환경 변수나 --aud/--iss 로 맞춘다.
DEFAULT_AUDIENCE = "esg-api"
DEFAULT_ISSUER = "https://edk.local.invalid"


def private_key() -> RSAPrivateKey:
    """키 쌍을 읽는다. 없으면 만든다."""
    if not PRIVATE_KEY_FILE.exists():
        KEY_DIR.mkdir(mode=0o700, exist_ok=True)
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        pem = key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        PRIVATE_KEY_FILE.touch(mode=0o600)
        PRIVATE_KEY_FILE.write_bytes(pem)
    key = serialization.load_pem_private_key(PRIVATE_KEY_FILE.read_bytes(), password=None)
    if not isinstance(key, RSAPrivateKey):
        raise SystemExit(f"{PRIVATE_KEY_FILE} 가 RSA 개인키가 아니다")
    return key


def public_key_line() -> str:
    """공개키 PEM 을 환경 변수에 넣을 수 있게 한 줄로(줄바꿈을 글자 둘 \\n 으로)."""
    pem = (
        private_key()
        .public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    )
    return pem.decode().replace("\n", "\\n")


def make_token(
    *, tenant: str, sub: str, role: str, name: str, ttl: int, audience: str | None = None, issuer: str | None = None
) -> str:
    payload = {
        "iss": issuer or os.environ.get("EDK_JWT_ISSUER") or DEFAULT_ISSUER,
        "aud": audience or os.environ.get("EDK_JWT_AUDIENCE") or DEFAULT_AUDIENCE,
        "sub": sub,
        "tenant_id": tenant,
        "role": role,
        "name": name,
        "exp": int(time.time()) + ttl,
    }
    return jwt.encode(payload, private_key(), algorithm="RS256")


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬에서 EDK 인 척: 키 쌍과 토큰")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("public-key", help="공개키를 한 줄로 낸다(없으면 키 쌍을 만든다)")
    token = commands.add_parser("token", help="서명한 토큰을 낸다")
    token.add_argument("--tenant", required=True)
    token.add_argument("--sub", default="dev-user-1")
    token.add_argument("--role", default="editor", choices=["admin", "editor", "viewer"])
    token.add_argument("--name", default="개발자")
    token.add_argument("--ttl", type=int, default=300, help="수명(초). 기본 5분")
    token.add_argument("--aud", default=None)
    token.add_argument("--iss", default=None)
    args = parser.parse_args()

    if args.command == "public-key":
        print(public_key_line())
    else:
        print(
            make_token(
                tenant=args.tenant,
                sub=args.sub,
                role=args.role,
                name=args.name,
                ttl=args.ttl,
                audience=args.aud,
                issuer=args.iss,
            )
        )


if __name__ == "__main__":
    main()
