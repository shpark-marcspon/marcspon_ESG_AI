#!/usr/bin/env bash
# MARI-TICK-504 (RPT-88 DD13 backstop, DD14 1층 ③ out-of-band 채널):
# 커밋 트레일러를 best-effort 포착해 maricom에 전달한다. 채널은 **둘**이고 서로 독립이다.
#
# ── 채널 A · 의미 엣지 선언 (504) ────────────────────────────────────────────
#   Ticket: <ticket id|MARI-TICK-###>        # 소스(택1, 1개)
#   Issue: <issue id|MARI-ISSUE-###>         # 소스(택1, 1개) — 티켓 없이 이슈에서 곧장 나온 작업
#   Affects: <id>[, <id>...]                 # 이 커밋이 건드린 대상
#   Derives-from: <id>[, <id>...]            # 이 작업이 비롯된 원천
#   Concerns: <id>[, <id>...]                # 이 작업의 주제
#   Supersedes: <id>[, <id>...]              # 이 작업이 대체하는 것
#
# 소스는 Ticket:/Issue: 중 **메시지에 먼저 나온 한 줄** — 키에 우열은 없다(둘 다 1급).
# 뒤따르는 소스 줄은 warn 후 무시한다(같은 키가 여러 개일 때와 같은 규율, MARI-ISSUE-242).
# 값은 id 또는 shortId만(콤마 구분 복수 허용) — prose 금지, 공백 포함 토큰은 skip(소스도 동일).
# v1 타깃은 시민(ticket/report/issue 등) 한정 — 모듈 결정적 id는 MARI-TICK-508.
#
# ── 채널 B · 결정 기록 (MARI-TICK-1152 / RPT-190 §2) ─────────────────────────
#   Rejected: / Constraint: / Directive:     # 전역 커밋 규약이 낳는 결정 트레일러
# 조건 셋이 **모두** 참일 때만 시민(소스)의 타임라인에 사실 행 하나를 남긴다:
#   ① 소스 트레일러 1  ② 결정 트레일러 ≥1  ③ Affects 타깃 ≥1
# ③이 커트라인인 이유: Affects 가 없는 결정은 국소 결정으로 보고 포착하지 않는다(RPT-190 §2).
# 이 행을 모아 읽던 큐 명령은 MARI-TICK-1208 로 걷혔다 — 사건 행과 이 포착은 그대로다(RPT-212 §9).
#
# ★ 두 채널은 서로를 막지 않는다: 엣지 선언이 0건이거나 실패해도 결정 기록은 시도하고, 그 역도
#   같다. 그래서 아래 흐름은 **먼저 전부 파싱하고, 그 다음 채널을 하나씩** 돈다 — 채널 A 의
#   조기 탈출이 채널 B 를 데려가지 않게(그 반대도).
#
# ── 재생 커밋은 포착하지 않는다 (MARI-ISSUE-660 ①) ─────────────────────────────
# rebase·cherry-pick 은 커밋을 새 sha 로 **다시 만든다** — 그때마다 post-commit 이 발화해 같은 결정 문장이
# 새 sha 로 또 기록됐다(09-14 병합 창 뒤 원장 decision_trailer 301행 중 「같은 시민 + 같은 문장」 둘째 이후 행 32 ·
# 같은 문장이 네 번 기록된 것도 있다). 그래서 **재료가 있는** 재생 커밋에서는 stderr 한 줄을 남기고 아무것도 쓰지 않는다.
# 자리는 「재료 없음」 조기 탈출 **뒤**다 — 트레일러 0 인 재생 커밋은 오늘처럼 조용히 지나간다(30 커밋 rebase 가 30줄을 내지 않게).
# 신호 넷 = `git rev-parse --git-path <이름>` 이 가리키는 `rebase-merge` · `rebase-apply` · `sequencer` · `CHERRY_PICK_HEAD` 중
# 하나라도 존재. `.git/…` 를 하드코딩하지 않는다 — 워크트리에선 `.git` 이 파일이고 상태는 `…/.git/worktrees/<이름>/` 아래에 산다.
# 실측(git 2.39.3 · 임시 저장소): rebase(기본 merge 백엔드) 재생 = `rebase-merge` · cherry-pick 한 개 = `CHERRY_PICK_HEAD` 만
# (`sequencer` 없음) · 여러 개 = `sequencer` + `CHERRY_PICK_HEAD` · `rebase --apply` 와 `merge --no-ff` 는 post-commit 발화 0 ·
# `commit --amend` 는 발화하고 재생 신호가 없다(재포착은 닫지 않은 알려진 축). `GIT_REFLOG_ACTION` 은 신호로 못 쓴다 — 재생
# 커밋 전부에서 unset 이었다(충돌 뒤 `--continue` 한 커밋만 `rebase (continue)`).
# `COMMIT_REF` 가 설정된 호출(백필 입구)은 skip 하지 않는다 — 백필은 재생 상태와 무관하게 과거 커밋을 읽는다.
# 비용: rebase `edit` 멈춤에서 사람이 **새로** 만든 커밋도 skip 된다(재생 상태 안이라 구별 못 함). 회수 = 백필
# (`node scripts/backfill-decision-trailers.mjs` — 원장에 있는 sha·같은 제목은 건너뛴다. 이 skip 은 그 규율을 실시간 입구에 맞춘 것이다).
# 이미 쌓인 재생 행은 지우지 않는다(사용자 판정 2026-09-28 · 밴드 sweep-rules). 그 행을 읽는 쪽에서 거르던 계산(규칙 1 큐)은
# MARI-TICK-1208 로 걷혔다 — 원장에는 같은 문장의 재생 행이 그대로 있으니, 이 사건을 다시 세는 소비처가 서면 거기서 접을 것.
# `decision_trailer` 사건 행은 남으므로 재생 skip 자체는 그대로 필요하다.
# 병합 커밋: clean `merge` 는 post-commit 을 부르지 않는다(기록 안 됨 — 이 skip 이전부터) · 충돌 병합을 `git commit` 으로 마무리하면
# 발화하고 기록된다(`MERGE_HEAD` 는 신호 넷 밖). skip 뒤에도 남는 기록(일반 커밋 때 이미 포착된 것)의 sha 는 **재생 전** sha 다 —
# main 의 조상이 아니다.
# 무효 조건: git 이 재생 상태 파일 이름을 바꾸거나, `rebase --apply` 가 post-commit 을 부르게 되면 이 신호 넷이 재생을 놓친다.
#
# post-commit은 절대 커밋을 방해하지 않는다: 모든 실패는 warn 후 exit 0.
set -u

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

warn() { echo "[semantic-trailers] $*" >&2; }

# 읽을 커밋. 기본은 HEAD(훅의 유일한 쓰임) — `COMMIT_REF` 는 **백필 드라이버 전용 입구**다
# (scripts/backfill-decision-trailers.sh). 파서를 두 벌 두지 않으려고 훅 자신을 과거 커밋에
# 재생시키는 것이라, 여기서 갈라지면 백필과 훅이 서로 다른 것을 포착하게 된다 — 갈래를 늘리지 말 것.
ref="${COMMIT_REF:-HEAD}"

msg=$(git log -1 --format=%B "$ref" 2>/dev/null) || exit 0
sha=$(git log -1 --format=%h "$ref" 2>/dev/null) || exit 0
subject=$(git log -1 --format=%s "$ref" 2>/dev/null) || subject=""

# git interpret-trailers는 "마지막 단락"만 트레일러 블록으로 취급한다 — 하우스 스타일은
# Constraint:/Ticket: 그룹과 Co-Authored-By 사이에 빈 줄을 두므로 의미 트레일러를 놓친다.
# 여기 6개 키 한정으로 메시지 전문을 라인 앵커 스캔한다. Issue: 는 prose 어두로도 흔한 편이라
# (Ticket: 보다는) 오탐 여지가 있으나, 값이 id 형식이 아니면 소스·타깃 모두 아래서 skip 된다.
trailers=$(printf '%s\n' "$msg" | grep -iE '^(Ticket|Issue|Affects|Derives-from|Concerns|Supersedes):') || trailers=""

# 결정 트레일러는 **별도 스캔**이다 — 위 6키 grep 에 얹으면 채널 A 의 파서가 알 수 없는 키를 만난다.
# 같은 라인 앵커·같은 대소문자 무시 규율.
decision_lines=$(printf '%s\n' "$msg" | grep -iE '^(Rejected|Constraint|Directive):') || decision_lines=""

# 어느 채널도 재료가 없으면 조용히 통과 (대부분의 커밋).
if [ -z "$trailers" ] && [ -z "$decision_lines" ]; then
  exit 0
fi

# 재생 커밋(rebase·cherry-pick)은 포착하지 않는다 — 머리 주석 「재생 커밋은 포착하지 않는다」(MARI-ISSUE-660 ①).
# 백필 입구(`COMMIT_REF`)는 재생 상태와 무관하다.
if [ -z "${COMMIT_REF:-}" ]; then
  for replay_state in rebase-merge rebase-apply sequencer CHERRY_PICK_HEAD; do
    replay_path=$(git rev-parse --git-path "$replay_state" 2>/dev/null) || continue
    if [ -e "$replay_path" ]; then
      warn "재생 커밋($replay_state) — 포착 skip (commit $sha) · 필요하면 node scripts/backfill-decision-trailers.mjs"
      exit 0
    fi
  done
fi

# shortId(MARI-TICK-503 류)는 sid:로 감싸 서버 해석에 위임, canonical id는 그대로.
normalize_ref() {
  local v="$1"
  case "$v" in
    sid:*) printf '%s' "$v" ;;
    *)
      if printf '%s' "$v" | grep -qE '^[A-Z][A-Z0-9]*(-[A-Z0-9]+)+-[0-9]+$'; then
        printf 'sid:%s' "$v"
      else
        printf '%s' "$v"
      fi
      ;;
  esac
}

trim() {
  local v="$1"
  v="${v#"${v%%[![:space:]]*}"}"
  v="${v%"${v##*[![:space:]]}"}"
  printf '%s' "$v"
}

# 셸 단일 인용 — dry-run 출력이 그대로 복사·실행되게(그리고 검증 스크립트가 shlex 로 되읽게).
# `printf '%q'` 는 공백까지 백슬래시로 흩어 놓아 사람이 못 읽는다.
shq() {
  local v=$1
  v=${v//\'/\'\\\'\'}
  printf "'%s'" "$v"
}

source_ref=""
# 소스가 티켓인지 이슈인지 — 채널 B 의 `history activity <entity-type>` 가 이 값을 쓴다.
# 서버가 받는 문자열이 그대로 'ticket'/'issue' 다(history/application/event-handlers/activity-subject.ts
# 의 SYSTEM_CITIZEN_SUBJECT_KIND 가 정본 — 그 키가 곧 와이어의 entityType).
source_kind=""
declarations=()
# 채널 B 가 details 에 싣는 Affects 타깃. ★ **`sid:` 접두를 떼어낸 원문 토큰**이다 — 훅이
# normalize_ref 로 붙이는 것도, **저자가 커밋 메시지에 직접 쓴 것도** 뗀다(둘 다 떼야 한다).
# 왜: oRPC 입력은 딥 워크로 `sid:` 를 canonical id 로 치환하고(shared/orpc/short-id-resolve.
# interceptor.ts — 필드명 스코핑을 의도적으로 기각한 설계다), 해석 못 하는 shortId 하나면 요청
# **전체가 404** 다. 즉 details 안의 `sid:` 는 「원문 기록」이 아니라 조회 요청이 되고, 타깃 하나가
# 안 풀리면 그 커밋의 결정 기록이 통째로 사라진다. 해석되면 값이 nanoid 로 조용히 바뀐다 — 「커밋이
# 뭐라고 적었나」를 남기려는 이 칸의 목적과 정반대다.
# ⚠️ 저자 표기를 오용으로 보지 말 것: CLAUDE.md 도 edges.md 도 shortId 엔 `sid:` 를 붙이라고 가르친다
#    (실측: main 최근 800 커밋의 `Affects:` 줄 124 개 중 25 개 = 20% 가 `sid:` 표기).
#    그래프 참조는 채널 A 가 이미 세우므로, 이 칸은 사람이 읽을 문자열이면 충분하다.
affects_raw=()

if [ -n "$trailers" ]; then
  while IFS= read -r line; do
    key="${line%%:*}"
    value="${line#*:}"
    key_lc=$(printf '%s' "$key" | tr '[:upper:]' '[:lower:]')

    predicate=""
    case "$key_lc" in
      ticket | issue)
        if [ -n "$source_ref" ]; then
          warn "소스 트레일러(Ticket:/Issue:)가 여러 개 — 먼저 나온 값만 사용"
          continue
        fi
        first=$(printf '%s' "$value" | cut -d',' -f1 | xargs 2>/dev/null)
        [ -z "$first" ] && continue
        # prose 어두("Issue: 이 커밋은 …")를 소스로 삼지 않는다 — 타깃과 같은 잣대.
        if printf '%s' "$first" | grep -qE '[ *?[]'; then
          warn "id 형식 아닌 소스 값 skip: '$first'"
          continue
        fi
        source_ref=$(normalize_ref "$first")
        source_kind="$key_lc"
        continue
        ;;
      affects) predicate="affects" ;;
      derives-from) predicate="derives_from" ;;
      concerns) predicate="concerns" ;;
      supersedes) predicate="supersedes" ;;
      *) continue ;;
    esac

    IFS=',' read -ra targets <<<"$value"
    for raw in "${targets[@]}"; do
      target=$(printf '%s' "$raw" | xargs)
      [ -z "$target" ] && continue
      # 공백/글롭 특수문자 포함 값은 id가 아니다 — skip (dedup case 패턴 오작동 방지 겸용).
      if printf '%s' "$target" | grep -qE '[ *?[]'; then
        warn "id 형식 아닌 값 skip: '$target'"
        continue
      fi
      declarations+=("${predicate}"$'\t'"$(normalize_ref "$target")")
      # B1: 저자가 직접 쓴 `sid:` 도 **떼어낸다**. normalize_ref 가 붙이는 것만 막아서는 부족했다 —
      #     이 레포의 `Affects:` 줄 다섯 중 하나가 이미 `sid:` 표기다(규약대로 쓴 것이다).
      [ "$predicate" = "affects" ] && affects_raw+=("${target#sid:}")
    done
  done <<<"$trailers"
fi

# 결정 트레일러 파싱 — value 는 **원문 그대로** 싣는다(앞뒤 공백만 다듬는다). 자르지 말 것:
# 그 문장이 결정의 본문이고, 잘린 근거는 다음 사람이 옳은 결정을 되돌리게 만든다.
decision_pairs=()
if [ -n "$decision_lines" ]; then
  while IFS= read -r line; do
    [ -z "$line" ] && continue
    key_lc=$(printf '%s' "${line%%:*}" | tr '[:upper:]' '[:lower:]')
    case "$key_lc" in
      rejected) key_norm="Rejected" ;;
      constraint) key_norm="Constraint" ;;
      directive) key_norm="Directive" ;;
      *) continue ;;
    esac
    value=$(trim "${line#*:}")
    [ -z "$value" ] && continue
    decision_pairs+=("${key_norm}"$'\x1f'"${value}")
  done <<<"$decision_lines"
fi

# 「채널 B 가 실제로 발화 가능한가」 — 조건 ②·③ 은 파싱이 끝난 지금 이미 안다. ★ 이 판정을 CLI
# 해석·소스 검사 **앞**에 둔다(2026-09-06 리뷰 S1·S2). 뒤에 두면, 전역 커밋 규약이 티켓 없는
# 커밋에도 쓰라고 시키는 `Constraint:`/`Rejected:` 만 달린 커밋(main 최근 400 중 45건 = 11%)이
# 「소스가 없어 skip」 경고를 매번 뱉는다 — 실제로는 skip 할 것이 애초에 0 이었다. 그런 거짓 경고는
# 진짜 경고(결정 기록 실패)를 묻는다. 「어느 채널도 할 일 없음 = 조용히 통과」가 main 의 계약이다.
b_ready=0
if [ ${#decision_pairs[@]} -gt 0 ] && [ ${#affects_raw[@]} -gt 0 ]; then
  b_ready=1
fi

if [ ${#declarations[@]} -eq 0 ] && [ "$b_ready" -eq 0 ]; then
  exit 0
fi

if [ -z "$source_ref" ]; then
  warn "트레일러가 있지만 소스(Ticket: 또는 Issue:)가 없어 skip (commit $sha)"
  exit 0
fi

# CLI 해석: 명시 override → 전역 maricom → 레포 로컬 빌드.
cli=()
if [ -n "${MARICOM_BIN:-}" ]; then
  cli=("$MARICOM_BIN")
elif command -v maricom >/dev/null 2>&1; then
  cli=(maricom)
else
  repo_root=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
  if [ -f "$repo_root/packages/cli/dist/index.js" ]; then
    cli=(node "$repo_root/packages/cli/dist/index.js")
  else
    warn "maricom CLI를 찾을 수 없어 skip (commit $sha)"
    exit 0
  fi
fi

run_declare() {
  if command -v timeout >/dev/null 2>&1; then
    timeout 10 "$@"
    return $?
  fi
  if command -v gtimeout >/dev/null 2>&1; then
    gtimeout 10 "$@"
    return $?
  fi
  # coreutils 부재 폴백(워치독): 서버 행이 post-commit 터미널을 무한 블록하지 않게.
  "$@" &
  local pid=$!
  local i=0
  while kill -0 "$pid" 2>/dev/null && [ "$i" -lt 100 ]; do
    sleep 0.1
    i=$((i + 1))
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null
    wait "$pid" 2>/dev/null
    return 124
  fi
  wait "$pid"
}

# ── 채널 A · 의미 엣지 선언 ─────────────────────────────────────────────────
ok=0
fail=0
seen=""
for entry in ${declarations[@]+"${declarations[@]}"}; do
  predicate="${entry%%$'\t'*}"
  target="${entry#*$'\t'}"
  dedup_key="${predicate}|${target}"
  case "$seen" in *"|${dedup_key}|"*) continue ;; esac
  seen="${seen}|${dedup_key}|"

  if [ "$DRY_RUN" -eq 1 ]; then
    printf '%s\n' "${cli[*]} edge add $source_ref $predicate $target --origin commit_trailer --commit $sha"
    continue
  fi

  if run_declare "${cli[@]}" edge add "$source_ref" "$predicate" "$target" \
    --origin commit_trailer --commit "$sha" >/dev/null 2>&1; then
    ok=$((ok + 1))
  else
    fail=$((fail + 1))
    warn "선언 실패: $source_ref -$predicate-> $target"
  fi
done

if [ "$DRY_RUN" -eq 0 ] && [ $((ok + fail)) -gt 0 ]; then
  warn "의미 엣지 ${ok}건 포착 (실패 ${fail}건, commit $sha)"
fi

# ── 채널 B · 결정 기록 ──────────────────────────────────────────────────────
# 조건 ②·③ 은 위(`b_ready`)에서 이미 판정했다 — 여기서 다시 세지 않는다. 서지 않았다면 채널 A 만
# 할 일이 있었다는 뜻이고, 아무 말 없이 넘어간다(Affects 없는 결정 = 국소 결정, 정상 경로다).
if [ "$b_ready" -eq 0 ]; then
  exit 0
fi

# JSON 조립은 **인터프리터에 맡긴다** — 순수 bash 로는 따옴표·역슬래시·유니코드 이스케이프가
# 깨진다(트레일러 value 엔 그 셋이 다 온다). 값은 argv 가 아니라 **환경변수**로 넘긴다:
# 인용 층이 하나 사라져 셸 이스케이프 사고가 원천적으로 없다. 구분자는 US(\x1f)/RS(\x1e) —
# 트레일러 값은 라인 앵커로 뽑은 **한 줄**이라 제어문자가 섞일 수 없다.
json_tool=""
if command -v python3 >/dev/null 2>&1; then
  json_tool="python3"
elif command -v node >/dev/null 2>&1; then
  json_tool="node"
else
  warn "python3·node 가 둘 다 없어 결정 기록 skip (commit $sha)"
  exit 0
fi

export DT_COMMIT="$sha"
export DT_SUBJECT="$subject"
DT_TRAILERS=""
for pair in ${decision_pairs[@]+"${decision_pairs[@]}"}; do
  DT_TRAILERS="${DT_TRAILERS}${pair}"$'\x1e'
done
export DT_TRAILERS
DT_AFFECTS=""
for target in ${affects_raw[@]+"${affects_raw[@]}"}; do
  DT_AFFECTS="${DT_AFFECTS}${target}"$'\x1e'
done
export DT_AFFECTS

if [ "$json_tool" = "python3" ]; then
  details=$(python3 -c '
import json, os, sys

def split(raw, sep="\x1e"):
    return [part for part in raw.split(sep) if part != ""]

trailers = []
for pair in split(os.environ.get("DT_TRAILERS", "")):
    key, _, value = pair.partition("\x1f")
    trailers.append({"key": key, "value": value})

sys.stdout.write(json.dumps({
    "commit": os.environ.get("DT_COMMIT", ""),
    "subject": os.environ.get("DT_SUBJECT", ""),
    "trailers": trailers,
    "affects": split(os.environ.get("DT_AFFECTS", "")),
}, ensure_ascii=False, separators=(",", ":")))
') || details=""
else
  details=$(node -e '
const split = (raw) => (raw || "").split("\x1e").filter((part) => part !== "");
const trailers = split(process.env.DT_TRAILERS).map((pair) => {
  const at = pair.indexOf("\x1f");
  return at < 0 ? { key: pair, value: "" } : { key: pair.slice(0, at), value: pair.slice(at + 1) };
});
process.stdout.write(JSON.stringify({
  commit: process.env.DT_COMMIT || "",
  subject: process.env.DT_SUBJECT || "",
  trailers,
  affects: split(process.env.DT_AFFECTS),
}));
') || details=""
fi

if [ -z "$details" ]; then
  warn "결정 기록 JSON 조립 실패 ($json_tool) — skip (commit $sha)"
  exit 0
fi

if [ "$DRY_RUN" -eq 1 ]; then
  # 인용까지 실어 그대로 복사·실행할 수 있게 한다(채널 A 의 무인용 echo 와 의도적으로 다르다 —
  # details 엔 따옴표·역슬래시가 온다).
  # ★ `echo` 가 아니라 `printf` 다 — 셸 echo 는 구현에 따라 백슬래시를 해석해 값에서 지운다
  #   (실측: 커밋 제목의 `\backslash` 가 `ackslash` 로 나갔다). 이 줄이 검증의 눈이므로 값이
  #   출력 단계에서 변형되면 안 된다.
  printf '%s\n' "${cli[*]} history activity $source_kind $source_ref --kind fact --action-type decision_trailer --details $(shq "$details") -m $(shq "$subject")"
  exit 0
fi

if run_declare "${cli[@]}" history activity "$source_kind" "$source_ref" \
  --kind fact --action-type decision_trailer --details "$details" -m "$subject" >/dev/null 2>&1; then
  warn "결정 기록 1건 포착 (${#decision_pairs[@]} 트레일러 · ${#affects_raw[@]} affects, commit $sha)"
else
  warn "결정 기록 실패: $source_kind $source_ref (commit $sha)"
fi

exit 0
