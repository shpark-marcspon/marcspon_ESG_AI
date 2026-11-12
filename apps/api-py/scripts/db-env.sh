# test-business.sh 와 test-security.sh 가 읽어 들이는 조각(혼자 돌리는 스크립트가 아니다).
# 저장소 맨 위의 .env 에서 DB 주소를 만드는 데 필요한 값만 꺼내, 두 역할의 주소를 변수에 담는다.
#
# .env 를 통째로 셸에 읽어 들이지(source) 않는다: EDK_JWT_PUBLIC_KEY 의 값(PEM 한 줄)에 빈칸이 있어
# 셸이 그 줄을 명령으로 읽다 멈춘다(「PUBLIC: command not found」). compose 는 .env 를 셸로 읽지 않아 탈이 없다.

env_value() { # <키>   .env 의 KEY=VALUE 줄에서 값을 꺼낸다. 없으면 멈춘다.
  local value
  value="$(sed -n "s/^$1=//p" ../../.env | tail -1)"
  [ -n "$value" ] || { echo ".env 에 $1 가 없다" >&2; exit 2; }
  printf '%s' "$value"
}

_host="127.0.0.1:$(env_value POSTGRES_PORT)"
_db="$(env_value POSTGRES_DB)_py"
# 앱 역할(esg_app): RLS 가 걸린다.   주인 역할: 테스트 DB 를 만들고 마이그레이션한다.
APP_DATABASE_URL="postgres://esg_app:$(env_value APP_DB_PASSWORD)@${_host}/${_db}"
OWNER_DATABASE_URL="postgres://$(env_value POSTGRES_OWNER_USER):$(env_value POSTGRES_OWNER_PASSWORD)@${_host}/${_db}"
