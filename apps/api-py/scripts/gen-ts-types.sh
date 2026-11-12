#!/usr/bin/env bash
# Python API 의 계약(OpenAPI)에서 프론트(TypeScript)가 쓸 타입을 만든다.   사용: apps/api-py/scripts/gen-ts-types.sh
#
#   <모듈>/api.py·schemas.py ──(manage.py export_openapi)──▶ generated/openapi.json ──(openapi-typescript)──▶ generated/api.d.ts
#
# 서버도 DB 도 띄우지 않는다. 경로나 응답의 꼴을 고쳤으면 이것을 다시 돌리고 생성물 셋을 같이 커밋한다
# (openapi.json 이 코드와 어긋나면 esgapi/config/tests/test_api_contract.py 가 잡는다).
# api.d.ts 를 만든 openapi.json 의 sha256 을 generated/api.d.ts.source-sha256 에 적어 둔다. 같은 테스트 파일이
# 「지금 openapi.json 의 sha256 = 적힌 값」을 잰다: openapi.json 만 다시 만들고 api.d.ts 를 잊으면 걸린다.
# 못 잡는 것: api.d.ts 를 손으로 고친 것.
# apps/web 에 잇지는 않았다: 「TS 서버가 아니어도 프론트가 타입을 받을 수 있다」는 것만 보인다.
set -euo pipefail
cd "$(dirname "$0")/.."

mkdir -p generated
# 테스트용 설정으로 돈다: 문서를 뽑는 데는 DB 도 진짜 키도 필요 없다(테스트 설정이 가짜 값을 채운다).
DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi > generated/openapi.json
# 버전을 고정해 받아 돌린다(이 저장소의 의존성으로 넣지 않는다). 네트워크가 필요하다.
pnpm dlx openapi-typescript@7.13.0 generated/openapi.json -o generated/api.d.ts
# api.d.ts 가 만들어진 뒤에만 적는다(위 줄이 실패하면 set -e 로 여기 닿지 않는다).
shasum -a 256 generated/openapi.json | cut -d' ' -f1 > generated/api.d.ts.source-sha256
