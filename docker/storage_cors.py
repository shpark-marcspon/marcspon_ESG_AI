"""개발 compose 의 저장소(Versity) 버킷에 CORS 규칙을 쓰고 끝나는 한 번짜리(compose 의 storage-cors).

브라우저는 우리 화면(웹 출처)에서 저장소(다른 출처)로 서명한 주소에 PUT 할 때, 버킷이 「이 출처는 받는다」고 답해야
요청을 보낸다. 그 답을 정하는 것이 이 규칙이다. curl·서버끼리의 요청은 CORS 와 상관없다(서명만 맞으면 받는다).

운영의 짝은 infra/terraform/modules/storage/main.tf 의 aws_s3_bucket_cors_configuration(같은 S3 API, 같은 규칙 모양).
값(출처)은 운영과 묶지 못한다: 운영은 배포 도메인(tfvars), 개발은 워크트리마다 다른 localhost 포트다. 모양(메서드·헤더·
노출·max_age)만 빠른 시험(esgapi/config/tests/test_compose_storage_cors.py)이 terraform 글과 맞춘다.

덮어쓰므로 몇 번 돌아도 같다. 키 값은 찍지 않는다. 표준 라이브러리와 boto3(api-py 이미지에 있다)만 쓴다.

★ 무효 조건: Versity 판(compose 의 storage 이미지, 지금 v1.8.0)이 바뀌어 버킷 CORS 저장·OPTIONS 판정이 달라지면
  다시 고른다. 배포 환경이 compose 로 뜨거나 terraform 규칙이 JSON 파일로 가면 그 파일을 둘이 읽게 한다.
"""

import os
import re
import sys
from typing import Any

ALLOWED_METHODS = ("PUT", "GET", "HEAD")
ALLOWED_HEADERS = ("*",)
EXPOSE_HEADERS = ("ETag",)
MAX_AGE_SECONDS = 3000

# 출처 하나: 스킴과 호스트(포트)뿐이다. 경로·끝 `/`·빈칸·`*` 는 받지 않는다.
ORIGIN = re.compile(r"^https?://[^/\s*]+$")

NEEDED = ("S3_ENDPOINT", "S3_BUCKET", "S3_REGION", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "STORAGE_CORS_ORIGINS")


def parse_origins(text: str) -> tuple[str, ...]:
    """쉼표 목록 → 출처들(받은 차례). 비었거나 `*`·경로·끝 `/`·겹침이 있으면 ValueError."""
    origins = tuple(part.strip() for part in text.split(",") if part.strip())
    if not origins:
        raise ValueError("허락 출처가 비었다(STORAGE_CORS_ORIGINS)")
    for origin in origins:
        if "*" in origin:
            raise ValueError(f"허락 출처에 * 는 쓰지 않는다: {origin}")
        if not ORIGIN.match(origin):
            raise ValueError(f"출처는 스킴://호스트[:포트] 꼴이다(경로·끝 / 없이): {origin}")
    if len(set(origins)) != len(origins):
        raise ValueError("허락 출처가 겹친다")
    return origins


def rule_for(origins: tuple[str, ...]) -> dict[str, Any]:
    """버킷에 쓸 규칙 하나. put_bucket_cors 에 넣는 것과 되읽어 대조하는 것이 이 dict 하나다."""
    return {
        "AllowedOrigins": list(origins),
        "AllowedMethods": list(ALLOWED_METHODS),
        "AllowedHeaders": list(ALLOWED_HEADERS),
        "ExposeHeaders": list(EXPOSE_HEADERS),
        "MaxAgeSeconds": MAX_AGE_SECONDS,
    }


def main() -> int:
    missing = [key for key in NEEDED if not os.environ.get(key)]
    if missing:
        print(f"storage-cors: 환경 변수가 없다: {', '.join(missing)}", file=sys.stderr)
        return 2
    try:
        origins = parse_origins(os.environ["STORAGE_CORS_ORIGINS"])
    except ValueError as err:
        print(f"storage-cors: {err}", file=sys.stderr)
        return 2

    import boto3
    from botocore.config import Config

    client: Any = boto3.client(
        "s3",
        endpoint_url=os.environ["S3_ENDPOINT"],
        region_name=os.environ["S3_REGION"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )
    bucket = os.environ["S3_BUCKET"]
    rule = rule_for(origins)
    client.put_bucket_cors(Bucket=bucket, CORSConfiguration={"CORSRules": [rule]})
    got = client.get_bucket_cors(Bucket=bucket)["CORSRules"]
    if [{key: value for key, value in found.items() if key in rule} for found in got] != [rule]:
        print("storage-cors: 되읽은 규칙이 쓴 규칙과 다르다", file=sys.stderr)
        return 1
    print(f"storage-cors: bucket={bucket} origins={len(origins)} methods={','.join(ALLOWED_METHODS)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
