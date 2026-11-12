#!/usr/bin/env bash
# infra/terraform 전체 확인. AWS 계정도 자격 증명도 쓰지 않는다.
#
#   infra/terraform/verify.sh
#
# 단계마다 무엇을 돌렸는지와 EXIT=<종료 코드> 를 찍는다. 전부 0 이면 마지막 줄이 EXIT=0 이다.
#
#   0. 자격 증명 환경 변수가 없는가      (있으면 아무것도 하지 않고 멈춘다)
#   1. fmt -check                        글의 모양이 표준인가
#   2. init -backend=false               공급자 플러그인을 받는다(상태 저장소에는 닿지 않는다)
#   3. validate                          문법과 자원 인자의 이름·꼴이 공급자의 정의와 맞는가
#   4. test                              모의 공급자 위에서 계획을 세워 값을 단언한다(tests/*.tftest.hcl)
#   5. 보안 그룹 규칙의 수               테스트가 못 보는 것: 누가 규칙 자원을 새로 더했는가
#   5-1. 모듈을 불러오는 곳             5 와 5-2 가 읽을 수 있는 곳(../../modules)에서만 불러오는가
#   5-2. 역할에 붙는 정책의 수           같은 까닭: 누가 역할에 정책을 하나 더 붙였는가
#   6. git                               상태 파일·플러그인·내 변수 파일이 저장소에 들어가지 않았는가
#
# 매번 envs/practice/.terraform 을 지우고 시작한다(깨끗한 상태에서 처음부터). 받은 플러그인은 저장소 루트의
# .tools/terraform-plugin-cache 에 남겨 두어 다시 받지 않는다. 그것까지 지우고 돌리려면:  rm -rf ../../.tools
set -uo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"
tf="bin/tf"
overall=0

step() {
  # step "<설명>" <명령...> : 명령을 돌리고 EXIT= 줄을 찍는다.
  local title="$1"
  shift
  echo
  echo "── $title"
  echo "\$ $*"
  "$@"
  local code=$?
  echo "EXIT=$code"
  if [ "$code" -ne 0 ]; then overall=1; fi
}

# ── 0. 자격 증명이 없는 채로 도는가 ──────────────────────────────────────────
# 이 스크립트는 실제 AWS 에 닿을 일이 없다. 자격 증명이 환경에 있으면 무언가 잘못 섞인 것이므로 멈춘다.
# (bin/tf 는 환경 변수를 컨테이너에 넘기지 않으므로 있어도 쓰이지 않지만, 「없는 채로 돈다」를 분명히 한다.)
# 변수의 이름만 보고 값은 읽거나 찍지 않는다. ~/.aws 는 열지 않는다.
check_no_credentials() {
  local found=""
  local name
  for name in AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_DEFAULT_PROFILE \
    AWS_WEB_IDENTITY_TOKEN_FILE AWS_ROLE_ARN AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI \
    AWS_SHARED_CREDENTIALS_FILE AWS_CONFIG_FILE; do
    if [ -n "${!name:-}" ]; then found="$found $name"; fi
  done
  if [ -n "$found" ]; then
    echo "AWS 자격 증명 환경 변수가 있다:$found"
    echo "이 확인은 자격 증명 없이 돈다. 그 변수들을 지운 셸에서 다시 돌린다(예: env -u AWS_PROFILE infra/terraform/verify.sh)."
    return 1
  fi
  echo "AWS 자격 증명 환경 변수 없음"
}

echo "── 0. 자격 증명 환경 변수가 없는가"
check_no_credentials
code=$?
echo "EXIT=$code"
if [ "$code" -ne 0 ]; then
  echo
  echo "멈춘다."
  echo "EXIT=1"
  exit 1
fi

# 깨끗한 상태에서 시작한다.
rm -rf envs/practice/.terraform

step "1. 모양" "$tf" fmt -check -recursive
step "2. 플러그인 받기" "$tf" -chdir=envs/practice init -backend=false -input=false -no-color
step "3. 문법과 인자" "$tf" -chdir=envs/practice validate -no-color
step "4. 모의 공급자 위의 테스트" "$tf" -chdir=envs/practice test -no-color

# ── 5. 보안 그룹 규칙의 수 ───────────────────────────────────────────────────
# 테스트는 이름을 아는 규칙의 값만 볼 수 있다. "DB 로 들어오는 규칙이 이 둘뿐인가"는 수를 세어야 안다.
# infra/terraform 아래의 모든 *.tf 를 글로 읽어(모듈을 어느 폴더에 두든 읽힌다), 들어오는 규칙(aws_vpc_security_group_ingress_rule)이 어느 보안 그룹에 몇 개 붙는지 센다.
# 규칙을 일부러 더했다면 아래 기대 수를 같이 고친다(그리고 tests/network.tftest.hcl 에 그 규칙의 단언을 더한다).
check_security_group_rules() {
  local fail=0

  # 규칙을 적는 다른 길(옛 자원, 보안 그룹 안에 적는 블록)은 쓰지 않는다. 쓰면 이 검사가 세지 못한다.
  if grep -rnE '^[[:space:]]*resource[[:space:]]+"aws_security_group_rule"' . --include='*.tf'; then
    echo "↑ aws_security_group_rule 자원이 있다. aws_vpc_security_group_ingress_rule / egress_rule 로 적는다."
    fail=1
  fi
  if grep -rnE '^[[:space:]]*((ingress|egress)[[:space:]]*(\{|=)|dynamic[[:space:]]+"(ingress|egress)")' . --include='*.tf'; then
    echo "↑ 보안 그룹 안에 적은 ingress/egress 가 있다. 규칙 하나를 자원 하나로 적는다."
    fail=1
  fi
  # 이 검사는 *.tf 만 읽는다. 같은 내용을 JSON 으로 적는 *.tf.json 과, 자원을 덮어쓰는 *_override.tf 는 받지 않는다.
  local unreadable
  unreadable="$(find . \( -name '*.tf.json' -o -name 'override.tf' -o -name '*_override.tf' \) -not -path './envs/practice/.terraform/*')"
  if [ -n "$unreadable" ]; then
    echo "이 검사가 읽지 못하는 꼴의 파일이 있다(*.tf.json, override 파일). *.tf 로 적는다:"
    echo "$unreadable"
    fail=1
  fi

  # 들어오는 규칙마다 "어느 보안 그룹에 붙는가"를 뽑는다. → 한 줄에 보안 그룹 이름 하나
  local targets
  targets="$(find . -name '*.tf' -not -path './envs/practice/.terraform/*' -print0 | xargs -0 awk '
    /^[[:space:]]*resource[[:space:]]+"aws_vpc_security_group_ingress_rule"/ { inside = 1 }
    inside && /^[[:space:]]*security_group_id[[:space:]]*=/ {
      value = $0
      sub(/^[^=]*=[[:space:]]*/, "", value)
      sub(/[[:space:]]*(#.*)?$/, "", value)
      print value
    }
    inside && /^}/ { inside = 0 }
  ')"

  # 꼴이 aws_security_group.<이름>.id 가 아닌 것(변수로 받은 id 등)은 셀 수 없으므로 실패로 본다.
  local odd
  odd="$(printf '%s\n' "$targets" | grep -vE '^aws_security_group\.[a-z_]+\.id$' | grep -v '^$' || true)"
  if [ -n "$odd" ]; then
    echo "들어오는 규칙이 붙는 보안 그룹을 읽을 수 없다(aws_security_group.<이름>.id 꼴이 아니다):"
    echo "$odd"
    fail=1
  fi

  local pair group expected actual
  # alb 는 80 과, count 로 켜고 끄는 443 을 합쳐 코드에 둘이 적혀 있다.
  for pair in alb:2 api:1 worker:0 database:2 redis:2; do
    group="${pair%%:*}"
    expected="${pair##*:}"
    actual="$(printf '%s\n' "$targets" | grep -cE "^aws_security_group\.${group}\.id$" || true)"
    if [ "$actual" -eq "$expected" ]; then
      echo "보안 그룹 $group: 들어오는 규칙 $actual 개 (기대 $expected)"
    else
      echo "보안 그룹 $group: 들어오는 규칙 $actual 개 — 기대는 $expected 개다."
      fail=1
    fi
  done

  # 위 다섯 말고 다른 보안 그룹에 붙은 규칙이 있으면 알린다.
  local others
  others="$(printf '%s\n' "$targets" | grep -E '^aws_security_group\.' | grep -vE '^aws_security_group\.(alb|api|worker|database|redis)\.id$' || true)"
  if [ -n "$others" ]; then
    echo "모르는 보안 그룹에 붙은 들어오는 규칙이 있다:"
    echo "$others"
    fail=1
  fi

  return "$fail"
}
step "5. 보안 그룹 규칙의 수" check_security_group_rules

# ── 5-1. 모듈을 불러오는 곳 ──────────────────────────────────────────────────
# 5 와 5-2 는 infra/terraform 아래의 *.tf 만 읽는다. 모듈을 그 밖(다른 폴더, 레지스트리, git 주소)에서 불러오면
# 그 안의 자원은 세지 못한다. 그래서 불러오는 곳을 ../../modules/<이름> 으로 한정한다.
# (source 가 한 줄 더 있다: versions.tf 의 공급자 주소 "hashicorp/aws". 그것은 받는다.)
check_module_sources() {
  local odd
  odd="$(find . \( -name '*.tf' -o -name '*.tftest.hcl' \) -not -path './envs/practice/.terraform/*' -print0 |
    xargs -0 grep -nE '^[[:space:]]*source[[:space:]]*=' |
    grep -vE 'source[[:space:]]*=[[:space:]]*"(hashicorp/aws|\.\./\.\./modules/[a-z_]+)"[[:space:]]*$' || true)"
  if [ -n "$odd" ]; then
    echo "../../modules/<이름> 이 아닌 곳에서 모듈을 불러온다:"
    echo "$odd"
    return 1
  fi
  echo "모듈은 전부 ../../modules/<이름> 에서 불러온다."
}
step "5-1. 모듈을 불러오는 곳" check_module_sources

# ── 5-2. 역할에 붙는 정책의 수 ───────────────────────────────────────────────
# 같은 까닭이다. 테스트는 이름을 아는 정책 셋(실행, api, worker)의 내용만 본다. 누가 역할에 정책을 하나 더 붙이면
# (예: 관리형 정책 AdministratorAccess) 테스트에는 보이지 않는다. 그래서 정책을 붙이는 자원의 수를 센다.
# 권한을 일부러 더했다면 기대 수를 고치고 tests/iam.tftest.hcl 에 그 정책의 단언을 더한다.
check_iam_policy_count() {
  local fail=0
  # 파일 이름에 공백이 있어도 깨지지 않게 find -print0 | xargs -0 로 넘긴다.
  count_resource() {
    find . -name '*.tf' -not -path './envs/practice/.terraform/*' -print0 |
      xargs -0 grep -hE "^[[:space:]]*resource[[:space:]]+\"$1\"" | wc -l | tr -d ' '
  }

  local pair kind expected actual
  for pair in aws_iam_role:3 aws_iam_role_policy:3 aws_iam_role_policy_attachment:0 aws_iam_role_policy_attachments_exclusive:0 \
    aws_iam_policy:0 aws_iam_policy_attachment:0 aws_iam_role_policies_exclusive:0; do
    kind="${pair%%:*}"
    expected="${pair##*:}"
    actual="$(count_resource "$kind")"
    if [ "$actual" -eq "$expected" ]; then
      echo "$kind: $actual 개 (기대 $expected)"
    else
      echo "$kind: $actual 개 — 기대는 $expected 개다."
      fail=1
    fi
  done

  # 역할 안에 정책을 적는 옛 인자도 쓰지 않는다.
  if find . -name '*.tf' -not -path './envs/practice/.terraform/*' -print0 |
    xargs -0 grep -nE '^[[:space:]]*(managed_policy_arns[[:space:]]*=|inline_policy[[:space:]]*\{|dynamic[[:space:]]+"inline_policy")'; then
    echo "↑ 역할 안에 적은 정책(managed_policy_arns, inline_policy)이 있다. aws_iam_role_policy 로 적는다."
    fail=1
  fi

  return "$fail"
}
step "5-2. 역할에 붙는 정책의 수" check_iam_policy_count

# ── 6. git: 저장소에 들어가면 안 되는 것 ─────────────────────────────────────
# 상태 파일(*.tfstate)에는 만든 자원의 속성이 통째로 들어 있고 비밀이 섞일 수 있다. 내 변수 파일(*.tfvars)도 넣지 않는다.
check_git() {
  local fail=0
  local pattern='(^|/)\.terraform/|\.tfstate($|\.)|\.tfvars(\.json)?$|(^|/)\.tools/|(^|/)crash\.log$|(^|/)tfplan$|\.tfplan$'

  local tracked
  tracked="$(git ls-files -- "$(git rev-parse --show-toplevel)" | grep -E "$pattern" || true)"
  if [ -n "$tracked" ]; then
    echo "git 이 추적하는 파일 가운데 넣으면 안 되는 것이 있다:"
    echo "$tracked"
    fail=1
  fi

  # 아직 추적하지 않지만 `git add` 하면 들어갈 것(= .gitignore 가 못 막는 것)
  local addable
  addable="$(git status --short --untracked-files=all -- "$(git rev-parse --show-toplevel)" | grep -E "$pattern" || true)"
  if [ -n "$addable" ]; then
    echo ".gitignore 가 막지 못하는 파일이 있다(git add 하면 들어간다):"
    echo "$addable"
    fail=1
  fi

  # 공급자 잠금 파일은 반대로 넣어야 한다. 지워지지 않았는지만 본다.
  if [ ! -f envs/practice/.terraform.lock.hcl ]; then
    echo "envs/practice/.terraform.lock.hcl 이 없다. 공급자 버전을 고정하는 파일이라 커밋해야 한다."
    fail=1
  fi

  if [ "$fail" -eq 0 ]; then
    echo "상태 파일·계획 파일·.terraform/·tfvars·.tools/ 가 추적되지 않고, .gitignore 가 막고 있다. 잠금 파일 있음."
  fi
  git status --short -- .
  return "$fail"
}
step "6. git 에 들어가면 안 되는 것" check_git

echo
if [ "$overall" -eq 0 ]; then
  echo "전부 통과"
else
  echo "실패한 단계가 있다"
fi
echo "EXIT=$overall"
exit "$overall"
