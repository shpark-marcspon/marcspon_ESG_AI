# ─────────────────────────────────────────────────────────────────────────────
# logs: 컨테이너가 표준 출력에 쓴 줄이 모이는 곳(CloudWatch Logs). `docker compose logs` 에 대응한다.
#
# 로그 그룹 = 기록을 담는 통. 컨테이너 종류마다 하나씩 둔다. 앱은 지금처럼 표준 출력에 쓰기만 하면 된다.
# 그룹을 미리 만들어 두는 까닭: ① 보관 기간을 정한다(안 정하면 영원히 쌓이고 저장 요금이 든다)
# ② 컨테이너의 실행 역할에 "그룹을 만드는 권한"까지 줄 필요가 없어진다.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}/api"
  retention_in_days = var.retention_in_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name}/worker"
  retention_in_days = var.retention_in_days
}

# 파서는 worker 와 같은 태스크에 살지만 기록은 따로 모은다(언어도 형식도 다르다).
resource "aws_cloudwatch_log_group" "parser" {
  name              = "/ecs/${var.name}/parser"
  retention_in_days = var.retention_in_days
}

resource "aws_cloudwatch_log_group" "migrate" {
  name              = "/ecs/${var.name}/migrate"
  retention_in_days = var.retention_in_days
}
