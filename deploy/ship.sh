#!/usr/bin/env bash
# 병합된 main 커밋 하나를 서버의 /srv/esg-demo/releases/<짧은 해시> 로 보내고 current 를 그쪽으로 바꾼다(밴드 DP1).
#   도는 자리: 운영 기계(esg-app 저장소 안 어디서든).   사용: deploy/ship.sh <ssh 대상> <커밋>
#   그 뒤 서버에서 /srv/esg-demo/current/deploy/up.sh (진행 중 실행 0 확인 → 다시 띄움).
# 보내는 것은 git archive(추적한 파일만 — .env·out/ 0). main 의 조상인 커밋만 받는다(병합 안 된 가지 0).
# 환경 변수: SSH_CMD(기본 ssh) · SHIP_ROOT(서버 쪽 뿌리, 기본 /srv/esg-demo — 둘째 벌(데모 고정판)은
#   SHIP_ROOT=/srv/esg-demo2, docs/deploy-demo.md 11절 D6 · 자기검증은 가짜 뿌리).
# 서버에 남기는 것: shared/DEPLOYED 에 「UTC 시각 해시」 한 줄 더함 · releases 는 최근 3개만(그 폴더 안만 지운다 —
#   current 가 가리키는 것은 지우지 않는다). shared/(.env)·backup/·도커 볼륨은 건드리지 않는다.
set -euo pipefail

[ "$#" -eq 2 ] || { echo "사용: deploy/ship.sh <ssh 대상> <커밋>" >&2; exit 2; }
target="$1"
ssh_cmd="${SSH_CMD:-ssh}"
root="${SHIP_ROOT:-/srv/esg-demo}"
case "$root" in /*) ;; *) echo "SHIP_ROOT 는 절대 경로" >&2; exit 2 ;; esac
case "$root" in *[!A-Za-z0-9/._-]*) echo "SHIP_ROOT 에 쓸 수 없는 글자" >&2; exit 2 ;; esac
full="$(git rev-parse --verify "$2^{commit}")"
short="$(git rev-parse --short=12 "$full")"
git merge-base --is-ancestor "$full" main || { echo "main 에 병합된 커밋이 아니다: $short" >&2; exit 1; }

remote="set -eu; root=$root; full=$full; short=$short"'
cd "$root"
[ -d releases ] && [ -d shared ] || { echo "서버 폴더가 없다 — deploy/bootstrap-host.sh 먼저" >&2; exit 1; }
d="releases/$short"
# current 를 갈아 끼운다(GNU mv -T 는 원자적, 없으면 ln -sfn — 자기검증의 맥)
swap() { ln -sfn "$1" current.next && { mv -T current.next current 2>/dev/null || { rm -f current.next; ln -sfn "$1" current; }; }; }
rm -rf "$d.part"
mkdir -p "$d.part"
tar -x -f - -C "$d.part"
if [ -e "$d" ]; then
  # 같은 해시를 다시 보냄: current 가 그 폴더를 가리킬 수 있으니 먼저 .part 로 옮긴 뒤 옛것을 지운다(리뷰 L2)
  swap "$root/$d.part"
  rm -rf "$d"
fi
mv "$d.part" "$d"
swap "$root/$d"
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $full" >> shared/DEPLOYED
keep=$(readlink -f current)
ls -1dt releases/*/ | sed "s:/\$::" | tail -n +4 | while read -r old; do
  case "$old" in releases/?*) ;; *) continue ;; esac
  [ "$(readlink -f "$old")" = "$keep" ] && continue
  rm -rf -- "$old"
done
echo "current -> $(readlink current)"
'

git archive --format=tar "$full" | $ssh_cmd "$target" "$remote"
echo "보냄: $short — 서버에서 $root/current/deploy/up.sh"
