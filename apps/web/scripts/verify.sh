#!/usr/bin/env bash
# apps/web 을 처음부터 끝까지 한 번에 확인한다.   사용: apps/web/scripts/verify.sh
# 단계마다 "EXIT=<종료 코드>" 줄을 낸다. 전부 EXIT=0 이어야 통과다.
# 실제 자료 없이(환경 변수 없이) 돈다. docker 를 쓰지 않는다. 서버를 부르지 않는다.
# 브라우저 테스트는 포트 하나를 잠깐 쓴다(기본 15174, WEB_TEST_PORT 로 바꾼다).
set -u
cd "$(dirname "$0")/../../.."

failed=0
step() {
  echo
  echo "▶ $*"
  "$@"
  local code=$?
  echo "EXIT=$code"
  [ "$code" -eq 0 ] || failed=1
  return "$code"
}

# apps/web 아래에 PDF 나 실제 자료가 들지 않았는가: 이미 든 것(추적 중)과 들려고 하는 것(새 파일, 고친 파일)을 다 본다.
# apps/web 아래만 본다(2026-10-08 사용자 결정, MARC-ISSUE-55): apps/api-py 는 공개 배출계수 사본과 골든을 일부러 품는다.
#   - 확장자가 .pdf 인 파일
#   - 실제 자료 폴더(.local-data) 아래의 파일
#   - 200KB 를 넘는 JSON (손으로 쓴 예시 자료는 몇 KB 다. pnpm 의 잠금 파일은 yaml 이라 해당 없다)
#   - 정답 필드("gold")나 실측에 쓴 계수 표의 id 가 든 JSON (검토 표의 실제 자료는 변환해서 git 밖에 둔다)
no_real_data() {
  local bad=0 file
  while IFS= read -r file; do
    [ -f "$file" ] || continue
    case "$file" in
      *.pdf | *.PDF) echo "PDF 가 저장소에 들었다: $file"; bad=1 ;;
      *.local-data/*) echo "실제 자료 폴더의 파일이 저장소에 들었다: $file"; bad=1 ;;
      *.json | *.jsonl)
        if [ "$(wc -c < "$file")" -gt 200000 ]; then echo "큰 JSON 이 저장소에 들었다: $file"; bad=1; fi
        if grep -qE '"gold"[[:space:]]*:|"(keiti-epd|defra-[0-9]+|epa-seef[^"]*|gir-[0-9]+|kr-ets[^"]*):' "$file"; then echo "실제 자료(정답 필드나 계수 표의 id)가 저장소에 들었다: $file"; bad=1; fi ;;
    esac
  done < <( { git ls-files -- apps/web; git status --porcelain --untracked-files=all -- apps/web | cut -c4-; } | sort -u )
  [ "$bad" -eq 0 ] && echo "PDF·실제 자료 없음"
  return "$bad"
}

step pnpm install --frozen-lockfile
step pnpm --filter @esg/web typecheck
step pnpm --filter @esg/web lint
step pnpm --filter @esg/web format:check
step pnpm --filter @esg/web test
step pnpm --filter @esg/web build
# 데모를 열지 않는 프로덕션 빌드(VITE_DEMOS 없이)에 데모 넷이 들지 않았는가(밴드 WC1 ③). 스스로 한 번 더 빌드한다.
step apps/web/scripts/check-no-demos.sh

# 실제 브라우저 테스트. 먼저 머리 없는 Chromium 을 받는다(이미 있으면 바로 끝난다).
step pnpm --filter @esg/web exec playwright install --only-shell chromium
step pnpm --filter @esg/web test:browser

step no_real_data

echo
if [ "$failed" -eq 0 ]; then echo "VERIFY=PASS"; else echo "VERIFY=FAIL"; fi
exit "$failed"
