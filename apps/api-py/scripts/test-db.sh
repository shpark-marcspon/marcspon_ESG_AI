#!/usr/bin/env bash
# DB 가 있어야 도는 두 층을 차례로 돌린다: 업무 층(워커 여럿) → 보안 층(직렬).   사용: apps/api-py/scripts/test-db.sh
# 두 층은 Django 가 붙는 역할이 달라(주인 / 앱) pytest 를 따로 부른다. 하나만 돌리려면 아래 두 스크립트를 직접 부른다.
set -uo pipefail
here="$(dirname "$0")"
failed=0
"$here/test-business.sh" -n 2 || failed=1
"$here/test-security.sh" || failed=1
exit "$failed"
