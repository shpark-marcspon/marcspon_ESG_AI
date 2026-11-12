# ─────────────────────────────────────────────────────────────────────────────
# compute: 컨테이너를 띄우는 곳(ECS on Fargate)과 그 앞의 로드밸런서(ALB).
# compose 의 api, worker, parser, migrate 에 대응한다.
#
# ★ TS 서버(node dist/api.js) 기준이라 api-py 로 다시 쓸 때까지 켜지 않는다 — sid:MARC-ISSUE-108
#   (envs/practice 의 enable_compute 기본 false. 켜도 HTTPS 인증서와 좁은 ALB 주소 범위가 없으면 계획이 서지 않는다.)
#
# ★ 스택에 따라 가장 많이 달라지는 모듈이다. 서버 틀이나 worker 의 형태(예: Lambda)가 바뀌면 여기를 고치거나 버린다.
#
# ECS 의 낱말 셋:
#   태스크 정의(task definition) : "이 이미지를, 이 환경 변수로, 이만한 크기로 띄워라"는 설계도. compose 의 서비스 한 칸.
#   태스크(task)                 : 설계도대로 떠 있는 것. 컨테이너 하나 이상의 묶음이고 네트워크 주소를 하나 갖는다.
#   서비스(service)              : "이 태스크를 N 벌 늘 띄워 둬라. 죽으면 다시 띄우고, 새 설계도가 오면 갈아 끼워라".
# Fargate 는 "서버를 우리가 관리하지 않는" 방식이다. 쓴 CPU·메모리·시간만큼 낸다.
#
# 배포 단위는 「서비스 둘, 컨테이너 셋」 + 한 번짜리 태스크 하나:
#   api 서비스    : 컨테이너 api                         ← ALB 가 요청을 넘긴다
#   worker 서비스 : 컨테이너 worker + parser (한 태스크)  ← 들어오는 길 없음. 큐에서 일을 꺼낸다
#   migrate       : 서비스가 아니다. 배포 때 한 번 돌리고 끝나는 태스크의 설계도만 둔다
# ─────────────────────────────────────────────────────────────────────────────

locals {
  parser_port = 8000
  api_port    = 3000

  # 443 리스너의 TLS 정책. 바꿀 때는 tests/compute.tftest.hcl 의 단언도 같이 바꾼다.
  alb_ssl_policy = "ELBSecurityPolicy-TLS13-1-2-2021-06"

  # api 와 worker 가 같이 받는 환경 변수. compose.yaml 의 x-server-env 와 같은 자리다.
  # 이름은 compose 그대로다(TS 서버 기준. compose 와 대조하던 테스트는 걷었다 — api-py 로 다시 쓸 때 다시 세운다, sid:MARC-ISSUE-108). 값만 AWS 의 것으로 바뀐다.
  # compose 에 있고 여기에 없는 것 넷 — 일부러 뺐다:
  #   S3_ENDPOINT, S3_PUBLIC_ENDPOINT          : 진짜 S3 에서는 비운다(SDK 가 AWS 주소를 스스로 쓴다)
  #   AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY : 키를 넣지 않는다. 태스크 역할이 권한을 준다
  server_environment = concat(
    [
      { name = "S3_BUCKET", value = var.uploads_bucket_name },
      { name = "S3_REGION", value = var.region },
      # 진짜 S3 는 https://버킷.s3.리전.amazonaws.com/키 꼴(virtual-hosted style)을 쓴다.
      { name = "S3_FORCE_PATH_STYLE", value = "false" },
      # ★ 한 태스크의 컨테이너들은 네트워크를 같이 쓴다(awsvpc). 그래서 파서를 localhost 로 만난다.
      # compose 에서는 서비스 이름(parser)이었다. api 는 파서를 부르지 않지만 같은 설정 검사를 지나므로 같은 값을 준다.
      { name = "PARSER_URL", value = "http://localhost:${local.parser_port}" },
      { name = "PARSER_TIMEOUT_MS", value = tostring(var.parser_timeout_ms) },
      { name = "QUEUE_ATTEMPTS", value = tostring(var.queue_attempts) },
      { name = "QUEUE_BACKOFF_MS", value = tostring(var.queue_backoff_ms) },
      { name = "WORKER_LOCK_MS", value = tostring(var.worker_lock_ms) },
    ],
    # Redis 모듈을 끄면 이 변수를 넣지 않는다(큐가 다른 것으로 바뀌면 그 주소를 여기에 더한다).
    var.redis_url == null ? [] : [
      { name = "REDIS_URL", value = var.redis_url },
    ],
  )

  # 비밀은 environment 가 아니라 secrets 에 적는다. 값이 아니라 "어디에 있는가"(ARN)를 적으면,
  # 컨테이너가 뜰 때 ECS 가 실행 역할로 값을 읽어 환경 변수로 넣어 준다. 태스크 정의에도 상태 파일에도 값이 없다.
  server_secrets = var.database_url_secret_arn == null ? [] : [
    { name = "DATABASE_URL", valueFrom = var.database_url_secret_arn },
  ]

  migrate_secrets = var.migrate_database_url_secret_arn == null ? [] : [
    { name = "MIGRATE_DATABASE_URL", valueFrom = var.migrate_database_url_secret_arn },
  ]
}

# 클러스터: 서비스와 태스크를 담는 이름표. Fargate 에서는 서버가 없으므로 그 자체로는 요금이 없다.
resource "aws_ecs_cluster" "main" {
  name = var.name
}

# ── 로드밸런서 (api 앞) ──────────────────────────────────────────────────────
#   인터넷 → [리스너 :443 HTTPS] → [대상 그룹] → api 태스크들의 :3000
#   인터넷 → [리스너 :80] → 443 으로 돌려보내기만(평문으로는 넘기지 않는다)

# ALB: 바깥의 요청을 받아 건강한 api 태스크에 나눠 준다. 공개 서브넷 둘에 걸쳐 선다.
resource "aws_lb" "api" {
  name               = "${var.name}-api"
  load_balancer_type = "application"
  internal           = false
  subnets            = var.public_subnet_ids
  security_groups    = [var.alb_security_group_id]

  # 규격에 맞지 않는 HTTP 헤더를 버린다(요청 밀반입 공격을 줄인다).
  drop_invalid_header_fields = true
}

# 대상 그룹: ALB 가 요청을 넘길 곳의 목록과, 그곳이 건강한지 확인하는 법.
# ECS 서비스가 태스크를 띄우고 내릴 때마다 이 목록에 넣고 뺀다.
resource "aws_lb_target_group" "api" {
  name     = "${var.name}-api"
  vpc_id   = var.vpc_id
  protocol = "HTTP"
  port     = local.api_port
  # Fargate 태스크는 저마다 IP 를 가지므로(awsvpc) 대상을 IP 로 적는다. instance 가 아니다.
  target_type = "ip"

  # ★ ALB 의 대상 확인은 /readyz 다: "기대는 것(DB, Redis, 저장소)까지 닿아 요청을 받을 수 있는가".
  # 실패하면 ALB 가 그 태스크에 요청을 보내지 않고, 계속 실패하면 ECS 가 태스크를 갈아 끼운다.
  # (컨테이너 자체의 상태 확인은 아래 태스크 정의의 /healthz 다. 둘을 나누는 까닭은 거기에 적었다.)
  health_check {
    path                = "/readyz"
    matcher             = "200"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  # 태스크를 내릴 때, 이미 받은 요청이 끝나기를 기다려 주는 시간(초). 기본 300 은 연습에는 너무 길다.
  deregistration_delay = 30
}

# 리스너 80: 평문 HTTP 는 api 로 넘기지 않고 443 으로 돌려보내기만 한다.
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.api.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      protocol    = "HTTPS"
      port        = "443"
      status_code = "HTTP_301"
    }
  }
}

# 리스너 443: HTTPS 로 받아 대상 그룹에 넘긴다. 인증서(ACM)의 ARN 이 없으면 계획 단계에서 실패한다.
# ALB 보안 그룹의 443 은 network 모듈의 enable_https_ingress 가 연다(envs/practice 가 compute 와 같이 켠다).
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.api.arn
  port              = 443
  protocol          = "HTTPS"
  # TLS 1.3 과 1.2 만 받는 정책 하나로 고정한다(ELB 문서의 「보안 정책」 표).
  ssl_policy      = local.alb_ssl_policy
  certificate_arn = var.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }

  lifecycle {
    precondition {
      condition     = var.certificate_arn != null && startswith(coalesce(var.certificate_arn, "-"), "arn:")
      error_message = "certificate_arn 이 없다(또는 ARN 꼴이 아니다). ALB 는 HTTPS(443)로만 받는다 — ACM 인증서의 ARN 을 준다."
    }
  }
}

# ── api ──────────────────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  requires_compatibilities = ["FARGATE"]
  # awsvpc: 태스크마다 VPC 의 사설 IP 를 하나 받는다. Fargate 에서는 이것만 된다.
  network_mode = "awsvpc"
  cpu          = var.api_cpu
  memory       = var.api_memory

  execution_role_arn = var.execution_role_arn
  task_role_arn      = var.api_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  # 컨테이너의 설계도. 이 JSON 의 꼴과 이름(camelCase)은 ECS 가 정한 것이다.
  container_definitions = jsonencode([
    {
      name      = "api"
      image     = var.server_image
      essential = true
      command   = ["node", "dist/api.js"]

      portMappings = [
        { containerPort = local.api_port, protocol = "tcp" },
      ]

      environment = concat(local.server_environment, [
        { name = "PORT", value = tostring(local.api_port) },
        # 종료 신호 뒤 하던 요청을 마칠 시간. 아래 stopTimeout 보다 짧아야 한다.
        { name = "SHUTDOWN_TIMEOUT_MS", value = "10000" },
      ])
      secrets = local.server_secrets

      # 컨테이너 상태 확인은 /healthz 다: "프로세스가 살아 있는가"만 본다. 실패하면 ECS 가 태스크를 죽이고 새로 띄운다.
      # /readyz 를 여기에 쓰면 DB 가 잠깐 끊겼을 때 멀쩡한 컨테이너를 전부 죽이게 된다. 그래서 나눈다.
      # 이미지에 curl 이 없어 compose 와 같이 node 로 부른다.
      healthCheck = {
        command     = ["CMD", "node", "-e", "fetch('http://127.0.0.1:${local.api_port}/healthz').then(r=>process.exit(r.ok?0:1),()=>process.exit(1))"]
        interval    = 10
        timeout     = 5
        retries     = 3
        startPeriod = 15
      }

      # compose 의 stop_grace_period. SIGTERM 을 보낸 뒤 이만큼 기다렸다가 강제로 죽인다(Fargate 상한 120초).
      stopTimeout = var.api_stop_timeout_seconds

      # 표준 출력을 CloudWatch Logs 로 보낸다.
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.api_log_group_name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "api"
        }
      }
    },
  ])
}

# 서비스: 위 설계도(태스크 정의)대로 api 태스크를 desired_count 벌 늘 띄워 둔다. 죽으면 다시 띄운다.
resource "aws_ecs_service" "api" {
  name            = "api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.task_subnet_ids
    security_groups  = [var.api_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  # ★ api 서비스만 대상 그룹에 붙는다. "api 라는 컨테이너의 3000 포트를 대상으로 넣어라".
  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = local.api_port
  }

  # 새로 뜬 태스크가 준비되기 전의 대상 확인 실패를 이 시간(초) 동안 눈감아 준다.
  health_check_grace_period_seconds = 60

  # 새 버전의 태스크가 계속 건강해지지 못하면 배포를 멈추고 앞 버전으로 되돌린다.
  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # 리스너가 있어야 대상 그룹이 ALB 에 붙은 것으로 친다. Terraform 이 스스로 알 수 없는 순서라 적어 준다.
  depends_on = [aws_lb_listener.https]
}

# ── worker (+ parser) ────────────────────────────────────────────────────────

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  # 태스크 전체의 크기. 아래 두 컨테이너가 나눠 쓴다(파서만 따로 늘릴 수 없다).
  cpu    = var.worker_cpu
  memory = var.worker_memory

  execution_role_arn = var.execution_role_arn
  task_role_arn      = var.worker_task_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = var.server_image
      essential = true
      command   = ["node", "dist/worker.js"]

      # 포트를 열지 않는다. worker 에게 요청을 보내는 곳은 없다.

      environment = concat(local.server_environment, [
        # 하던 작업을 마칠 시간. 파서를 기다리는 최대 시간보다 길고, 아래 stopTimeout 보다 짧아야 한다.
        { name = "SHUTDOWN_TIMEOUT_MS", value = "40000" },
      ])
      secrets = local.server_secrets

      # compose 의 depends_on. 같은 태스크 안에서만 쓸 수 있다: 파서가 건강해진 뒤에 worker 를 띄운다.
      # HEALTHY 조건은 기다리는 상대(parser)에 healthCheck 가 있어야 성립한다.
      dependsOn = [
        { containerName = "parser", condition = "HEALTHY" },
      ]

      stopTimeout = var.worker_stop_timeout_seconds

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.worker_log_group_name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "worker"
        }
      }
    },
    {
      name  = "parser"
      image = var.parser_image
      # essential = true: 파서가 죽으면 태스크 전체를 내리고 새로 띄운다(worker 혼자서는 일을 못 한다).
      essential = true

      # ★ portMappings 를 적지 않는다. 파서의 8000 포트는 같은 태스크의 worker 만 localhost 로 부른다.
      # 그리고 worker 의 보안 그룹에는 들어오는 규칙이 없다(network 모듈). 바깥에서 닿을 길이 둘 다 없다.

      healthCheck = {
        command     = ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${local.parser_port}/healthz', timeout=2)"]
        interval    = 10
        timeout     = 5
        retries     = 3
        startPeriod = 15
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.parser_log_group_name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "parser"
        }
      }
    },
  ])
}

# 서비스: worker 태스크(worker + parser)를 desired_count 벌 늘 띄워 둔다.
resource "aws_ecs_service" "worker" {
  name            = "worker"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.task_subnet_ids
    security_groups  = [var.worker_security_group_id]
    assign_public_ip = var.assign_public_ip
  }

  # ★ load_balancer 블록이 없다. worker 는 로드밸런서에 붙지 않는다.

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }
}

# ── migrate (한 번짜리) ──────────────────────────────────────────────────────
# 서비스가 없다. 설계도만 두고, 배포 때 사람이나 파이프라인이 `aws ecs run-task` 로 한 번 돌린다.
# 성공(종료 코드 0)을 확인한 뒤에 api 와 worker 를 새 버전으로 바꾼다. 돌리는 명령은 infra/README.md 에 있다.
# 태스크 역할이 없다: 마이그레이션은 DB 만 만지고 AWS 의 다른 것을 부르지 않는다.

resource "aws_ecs_task_definition" "migrate" {
  family                   = "${var.name}-migrate"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512

  execution_role_arn = var.execution_role_arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = var.cpu_architecture
  }

  container_definitions = jsonencode([
    {
      name      = "migrate"
      image     = var.server_image
      essential = true
      command   = ["node", "dist/migrate.js"]

      # 주인 역할의 주소 하나만 받는다. api 와 worker 에는 이 주소를 주지 않는다.
      environment = []
      secrets     = local.migrate_secrets

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = var.migrate_log_group_name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "migrate"
        }
      }
    },
  ])
}
