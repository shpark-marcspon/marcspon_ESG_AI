#!/usr/bin/env bash
# LLM 공급사 키(마크스폰 키)를 서버의 .env 에 넣고 실행 모드를 live 로 바꾼다(밴드 DP1). 도는 자리: 운영 기계.
#   사용: deploy/put-llm-key.sh <ssh 대상>            키를 넣고 LLM_RUN_MODE=live
#         deploy/put-llm-key.sh <ssh 대상> --mock     키는 두고 LLM_RUN_MODE 를 비움(mock — 멈춤 조건에서 실호출을 끊을 때)
#   그 뒤 서버에서 deploy/up.sh 로 다시 띄워야 컨테이너에 닿는다.
# 환경 변수: KEY_FILE(기본 ~/.config/marcspon-openai.env — 줄 OPENAI_API_KEY=…) · SSH_CMD(기본 ssh) ·
#   ENV_PATH(서버 쪽 파일, 기본 /srv/esg-demo/shared/.env).
# 키는 서브셸 안에서만 읽고 ssh 의 표준 입력으로만 보낸다: 명령줄 인자·ps·셸 기록·화면·임시 파일(운영 기계) 0.
#   서버 쪽은 .env 의 LLM_OPENAI_API_KEY= 줄만 바꿔 같은 폴더의 600 임시 파일 → mv(원자적). 찍는 것은 「값 있음」뿐.
set -euo pipefail
set +x

usage() { echo "사용: deploy/put-llm-key.sh <ssh 대상> [--mock]" >&2; exit 2; }
[ "$#" -ge 1 ] && [ "$#" -le 2 ] || usage
target="$1" mode=live
if [ "$#" -eq 2 ]; then [ "$2" = --mock ] || usage; mode=mock; fi
key_file="${KEY_FILE:-$HOME/.config/marcspon-openai.env}"
env_path="${ENV_PATH:-/srv/esg-demo/shared/.env}"
ssh_cmd="${SSH_CMD:-ssh}"
case "$env_path" in /*) ;; *) echo "ENV_PATH 는 절대 경로여야 한다" >&2; exit 2 ;; esac
case "$env_path" in *"'"*) echo "ENV_PATH 에 작은따옴표를 쓰지 않는다" >&2; exit 2 ;; esac

# 서버 쪽에서 도는 글(비밀 0 — 키는 표준 입력 한 줄로 온다). MODE=live 면 키를 받아 넣고, mock 이면 모드만 비운다.
remote="set -eu; umask 077; f='$env_path'; MODE=$mode"'
[ -f "$f" ] || { echo "서버에 .env 가 없다: $f" >&2; exit 1; }
if [ "$MODE" = live ]; then IFS= read -r K || true; else K=; fi
if [ "$MODE" = live ] && [ -z "$K" ]; then echo "받은 키가 비었다 — 바꾸지 않음" >&2; exit 1; fi
t=$(mktemp "$f.new.XXXXXX")
trap '"'"'rm -f "$t"'"'"' EXIT
K="$K" MODE="$MODE" awk '"'"'
  BEGIN { seen_key = 0; seen_mode = 0 }
  /^LLM_OPENAI_API_KEY=/ { seen_key = 1; if (ENVIRON["MODE"] == "live") { print "LLM_OPENAI_API_KEY=" ENVIRON["K"]; next } }
  /^LLM_RUN_MODE=/ { seen_mode = 1; print "LLM_RUN_MODE=" (ENVIRON["MODE"] == "live" ? "live" : ""); next }
  { print }
  END { if (!seen_key || !seen_mode) { print "틀에 LLM_OPENAI_API_KEY= 나 LLM_RUN_MODE= 줄이 없다" > "/dev/stderr"; exit 1 } }
'"'"' "$f" > "$t"
mv "$t" "$f"
trap - EXIT
if grep -q "^LLM_OPENAI_API_KEY=." "$f"; then echo "LLM_OPENAI_API_KEY 값 있음"; else echo "LLM_OPENAI_API_KEY 값 없음"; fi
grep "^LLM_RUN_MODE=" "$f"
'

if [ "$mode" = mock ]; then
  $ssh_cmd "$target" "$remote" < /dev/null
  exit
fi

[ -r "$key_file" ] || { echo "키 파일을 읽을 수 없다: $key_file" >&2; exit 1; }
(
  set +x
  value="$(sed -n -e 's/^export //' -e 's/^OPENAI_API_KEY=//p' "$key_file" | head -n 1 | tr -d "\"'\r")"
  [ -n "$value" ] || { echo "키 파일에 OPENAI_API_KEY= 줄이 없거나 비었다" >&2; exit 1; }
  printf '%s\n' "$value" | $ssh_cmd "$target" "$remote"
)
