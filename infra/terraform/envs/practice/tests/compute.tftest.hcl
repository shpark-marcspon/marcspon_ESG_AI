# (라) worker 태스크 정의: 컨테이너 둘(worker, 파서), worker 가 파서를 기다림, 파서의 포트는 바깥에 안 열림, PARSER_URL 이 localhost.
# (마) api 서비스만 ALB 대상 그룹에 붙고 worker 는 안 붙음. 대상 그룹 상태 확인 경로 /readyz.
# (사) 비밀은 secrets 로(값이 아니라 위치), 환경 변수의 값.
# (아) compute 막기: 기본값으로는 compute 가 없음, 켜도 /0 이나 인증서 없음은 계획이 서지 않음, 80 은 443 으로 돌려보내기만.
#
# compose.yaml 의 TS 서비스와 환경 변수 이름을 대조하던 run 은 걷었다 — 대조할 짝(compose 의 TS 서비스)이 사라졌다.
# api-py 기준으로 다시 쓸 때 다시 세운다(sid:MARC-ISSUE-108).
#
# 태스크 정의의 컨테이너 부분(container_definitions)은 JSON 글자다. jsondecode 로 풀어서 본다.
# [0] 은 첫 번째 컨테이너다: api 태스크는 [api], worker 태스크는 [worker, parser], migrate 태스크는 [migrate].

mock_provider "aws" {
  override_during = plan

  mock_resource "aws_lb_target_group" {
    defaults = {
      # 000000000000 은 가짜 계정 번호다.
      arn = "arn:aws:elasticloadbalancing:ap-northeast-2:000000000000:targetgroup/test-api/0000000000000000"
    }
  }
}

variables {
  name   = "test"
  region = "ap-northeast-2"

  vpc_id                   = "vpc-test"
  public_subnet_ids        = ["subnet-public-a", "subnet-public-b"]
  task_subnet_ids          = ["subnet-public-a", "subnet-public-b"]
  assign_public_ip         = true
  alb_security_group_id    = "sg-alb"
  api_security_group_id    = "sg-api"
  worker_security_group_id = "sg-worker"

  execution_role_arn   = "arn:aws:iam::000000000000:role/test-task-execution"
  api_task_role_arn    = "arn:aws:iam::000000000000:role/test-api-task"
  worker_task_role_arn = "arn:aws:iam::000000000000:role/test-worker-task"

  server_image = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/test/server:abc1234"
  parser_image = "000000000000.dkr.ecr.ap-northeast-2.amazonaws.com/test/parser:abc1234"

  api_log_group_name     = "/ecs/test/api"
  worker_log_group_name  = "/ecs/test/worker"
  parser_log_group_name  = "/ecs/test/parser"
  migrate_log_group_name = "/ecs/test/migrate"

  uploads_bucket_name             = "test-uploads-bucket"
  redis_url                       = "rediss://test-redis.example.internal:6379"
  database_url_secret_arn         = "arn:aws:secretsmanager:ap-northeast-2:000000000000:secret:test/database-url-AbCdEf"
  migrate_database_url_secret_arn = "arn:aws:secretsmanager:ap-northeast-2:000000000000:secret:test/migrate-database-url-AbCdEf"

  # 가짜 인증서. 443 리스너는 이것이 없으면 계획이 서지 않는다.
  certificate_arn = "arn:aws:acm:ap-northeast-2:000000000000:certificate/00000000-0000-0000-0000-000000000000"
}

# ── (라) ─────────────────────────────────────────────────────────────────────

run "worker_task_has_worker_and_parser_talking_over_localhost" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  # 컨테이너는 정확히 둘: worker, parser
  assert {
    condition     = [for c in jsondecode(aws_ecs_task_definition.worker.container_definitions) : c.name] == ["worker", "parser"]
    error_message = "worker 태스크의 컨테이너가 [worker, parser] 가 아니다."
  }

  # worker 가 파서를 기다린다(건강해질 때까지)
  assert {
    condition = jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].dependsOn == [
      { containerName = "parser", condition = "HEALTHY" },
    ]
    error_message = "worker 컨테이너가 파서가 건강해지기를 기다리지 않는다(dependsOn)."
  }

  # HEALTHY 를 기다리려면 파서에 상태 확인이 있어야 한다. 없으면 worker 가 영영 뜨지 않는다.
  assert {
    condition     = strcontains(join(" ", jsondecode(aws_ecs_task_definition.worker.container_definitions)[1].healthCheck.command), "http://127.0.0.1:8000/healthz")
    error_message = "파서 컨테이너에 상태 확인(/healthz)이 없다."
  }

  # 파서의 포트는 바깥에 안 열린다: 포트 매핑이 없다(worker 도 없다).
  assert {
    condition = alltrue([
      for c in jsondecode(aws_ecs_task_definition.worker.container_definitions) :
      length(try(c.portMappings, [])) == 0
    ])
    error_message = "worker 태스크의 컨테이너에 포트 매핑이 있다. 파서는 같은 태스크의 worker 만 localhost 로 부른다."
  }

  # PARSER_URL 이 localhost 다(같은 태스크 안).
  assert {
    condition = [
      for e in jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].environment : e.value
      if e.name == "PARSER_URL"
    ] == ["http://localhost:8000"]
    error_message = "worker 의 PARSER_URL 이 http://localhost:8000 이 아니다."
  }

  # 한 태스크의 컨테이너가 localhost 로 만나려면 네트워크 모드가 awsvpc 여야 한다.
  assert {
    condition     = aws_ecs_task_definition.worker.network_mode == "awsvpc" && aws_ecs_task_definition.worker.requires_compatibilities == toset(["FARGATE"])
    error_message = "worker 태스크 정의가 Fargate + awsvpc 가 아니다."
  }

  # 둘 다 essential: 하나가 죽으면 태스크를 새로 띄운다.
  assert {
    condition     = alltrue([for c in jsondecode(aws_ecs_task_definition.worker.container_definitions) : c.essential])
    error_message = "worker 태스크에 essential 이 아닌 컨테이너가 있다."
  }

  # 실행 명령과 이미지
  assert {
    condition = (
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].command == ["node", "dist/worker.js"] &&
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].image == var.server_image &&
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[1].image == var.parser_image
    )
    error_message = "worker 컨테이너의 명령이나 이미지, 또는 파서의 이미지가 다르다."
  }

  # 종료 유예: Fargate 상한(120초) 안이고, 앱이 하던 일을 마치는 시간(SHUTDOWN_TIMEOUT_MS)보다 길다.
  assert {
    condition = (
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].stopTimeout <= 120 &&
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].stopTimeout * 1000 > tonumber([
        for e in jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].environment : e.value
        if e.name == "SHUTDOWN_TIMEOUT_MS"
      ][0])
    )
    error_message = "worker 의 stopTimeout 이 120초를 넘거나 SHUTDOWN_TIMEOUT_MS 보다 짧다."
  }

  # 역할: worker 태스크는 worker 의 태스크 역할을 쓴다.
  assert {
    condition     = aws_ecs_task_definition.worker.task_role_arn == var.worker_task_role_arn && aws_ecs_task_definition.worker.execution_role_arn == var.execution_role_arn
    error_message = "worker 태스크 정의의 역할이 다르다."
  }

  # 기록: 컨테이너마다 자기 로그 그룹으로 보낸다. 로그 설정이 빠지면 표준 출력이 어디에도 남지 않는다.
  assert {
    condition = [
      for c in jsondecode(aws_ecs_task_definition.worker.container_definitions) : c.logConfiguration.options["awslogs-group"]
    ] == [var.worker_log_group_name, var.parser_log_group_name]
    error_message = "worker·파서 컨테이너의 로그 그룹이 다르거나 로그 설정이 없다."
  }
}

# ── (마) ─────────────────────────────────────────────────────────────────────

run "only_api_service_is_behind_the_load_balancer" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  # api 서비스: 대상 그룹 하나에, api 컨테이너의 3000 포트로 붙는다.
  assert {
    condition     = length(aws_ecs_service.api.load_balancer) == 1
    error_message = "api 서비스가 대상 그룹에 붙어 있지 않다(또는 둘 이상에 붙었다)."
  }

  assert {
    condition = alltrue([
      for lb in aws_ecs_service.api.load_balancer :
      lb.target_group_arn == aws_lb_target_group.api.arn && lb.container_name == "api" && lb.container_port == 3000
    ])
    error_message = "api 서비스가 붙은 대상 그룹·컨테이너·포트가 다르다."
  }

  # worker 서비스: 붙지 않는다.
  assert {
    condition     = length(aws_ecs_service.worker.load_balancer) == 0
    error_message = "worker 서비스가 로드밸런서에 붙어 있다. worker 로 들어오는 요청은 없다."
  }

  # 대상 그룹의 상태 확인은 /readyz, 대상은 IP(awsvpc).
  assert {
    condition     = aws_lb_target_group.api.health_check[0].path == "/readyz" && aws_lb_target_group.api.health_check[0].matcher == "200"
    error_message = "대상 그룹의 상태 확인 경로가 /readyz(200)가 아니다."
  }

  assert {
    condition     = aws_lb_target_group.api.target_type == "ip" && aws_lb_target_group.api.port == 3000 && aws_lb_target_group.api.protocol == "HTTP"
    error_message = "대상 그룹이 IP 대상 / 3000 / HTTP 가 아니다."
  }

  # 컨테이너 상태 확인은 /healthz 로 나눈다(DB 가 잠깐 끊겼다고 컨테이너를 죽이지 않게).
  assert {
    condition     = strcontains(join(" ", jsondecode(aws_ecs_task_definition.api.container_definitions)[0].healthCheck.command), "/healthz")
    error_message = "api 컨테이너의 상태 확인이 /healthz 가 아니다."
  }

  # 대상 그룹으로 넘기는 리스너는 443(HTTPS) 하나다. 80 은 돌려보내기만 한다(아래 (아)).
  assert {
    condition     = aws_lb_listener.https.default_action[0].type == "forward" && aws_lb_listener.https.default_action[0].target_group_arn == aws_lb_target_group.api.arn
    error_message = "443 리스너가 api 대상 그룹으로 넘기지 않는다."
  }

  # 서비스가 다는 보안 그룹과 서브넷
  assert {
    condition = (
      aws_ecs_service.api.network_configuration[0].security_groups == toset(["sg-api"]) &&
      aws_ecs_service.worker.network_configuration[0].security_groups == toset(["sg-worker"]) &&
      aws_ecs_service.api.network_configuration[0].assign_public_ip == var.assign_public_ip &&
      aws_ecs_service.worker.network_configuration[0].assign_public_ip == var.assign_public_ip &&
      aws_ecs_service.api.network_configuration[0].subnets == toset(var.task_subnet_ids) &&
      aws_ecs_service.worker.network_configuration[0].subnets == toset(var.task_subnet_ids)
    )
    error_message = "서비스의 보안 그룹·서브넷·공인 IP 설정이 넘겨받은 값과 다르다."
  }

  # ALB 는 공개 서브넷에, ALB 의 보안 그룹만 달고 선다.
  assert {
    condition     = aws_lb.api.internal == false && aws_lb.api.subnets == toset(var.public_subnet_ids) && aws_lb.api.security_groups == toset(["sg-alb"])
    error_message = "ALB 의 서브넷이나 보안 그룹이 다르다."
  }

  # api 컨테이너: 포트 3000 하나, 명령, 역할, 기록
  assert {
    condition = (
      [for p in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].portMappings : p.containerPort] == [3000] &&
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].command == ["node", "dist/api.js"] &&
      aws_ecs_task_definition.api.task_role_arn == var.api_task_role_arn &&
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].logConfiguration.options["awslogs-group"] == var.api_log_group_name
    )
    error_message = "api 컨테이너의 포트·명령·역할·로그 그룹이 다르다."
  }

  assert {
    condition = (
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].stopTimeout <= 120 &&
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].stopTimeout * 1000 > tonumber([
        for e in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment : e.value
        if e.name == "SHUTDOWN_TIMEOUT_MS"
      ][0])
    )
    error_message = "api 의 stopTimeout 이 120초를 넘거나 SHUTDOWN_TIMEOUT_MS 보다 짧다."
  }
}

# ── (사) ─────────────────────────────────────────────────────────────────────

run "db_url_is_a_secret_and_env_values" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  # 값: 비밀은 secrets 로(값이 아니라 위치), 진짜 S3 에 맞는 값.
  assert {
    condition = (
      jsondecode(aws_ecs_task_definition.api.container_definitions)[0].secrets == [{ name = "DATABASE_URL", valueFrom = var.database_url_secret_arn }] &&
      jsondecode(aws_ecs_task_definition.worker.container_definitions)[0].secrets == [{ name = "DATABASE_URL", valueFrom = var.database_url_secret_arn }] &&
      jsondecode(aws_ecs_task_definition.migrate.container_definitions)[0].secrets == [{ name = "MIGRATE_DATABASE_URL", valueFrom = var.migrate_database_url_secret_arn }]
    )
    error_message = "DB 접속 주소가 secrets 로 들어가지 않거나 가리키는 비밀이 다르다. api·worker 는 DATABASE_URL 만, migrate 는 MIGRATE_DATABASE_URL 만 받는다."
  }

  assert {
    condition = { for e in jsondecode(aws_ecs_task_definition.api.container_definitions)[0].environment : e.name => e.value } == {
      S3_BUCKET           = "test-uploads-bucket"
      S3_REGION           = "ap-northeast-2"
      S3_FORCE_PATH_STYLE = "false"
      PARSER_URL          = "http://localhost:8000"
      PARSER_TIMEOUT_MS   = "30000"
      QUEUE_ATTEMPTS      = "3"
      QUEUE_BACKOFF_MS    = "1000"
      WORKER_LOCK_MS      = "30000"
      REDIS_URL           = "rediss://test-redis.example.internal:6379"
      PORT                = "3000"
      SHUTDOWN_TIMEOUT_MS = "10000"
    }
    error_message = "api 컨테이너의 환경 변수 값이 기대와 다르다."
  }
}

# ── 꺼진 모듈의 값이 null 로 올 때 ───────────────────────────────────────────

run "env_is_omitted_when_redis_and_database_are_off" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  variables {
    redis_url                       = null
    database_url_secret_arn         = null
    migrate_database_url_secret_arn = null
  }

  assert {
    condition = alltrue([
      for c in concat(
        jsondecode(aws_ecs_task_definition.api.container_definitions),
        [jsondecode(aws_ecs_task_definition.worker.container_definitions)[0]],
        jsondecode(aws_ecs_task_definition.migrate.container_definitions),
      ) :
      length(c.secrets) == 0 && !contains([for e in c.environment : e.name], "REDIS_URL")
    ])
    error_message = "Redis·DB 를 껐는데 REDIS_URL 이나 비밀이 태스크 정의에 남아 있다."
  }
}

# ── (아) compute 막기 ────────────────────────────────────────────────────────
# compute 모듈은 TS 서버 기준이라 api-py 로 다시 쓸 때까지 켜지 않는다(sid:MARC-ISSUE-108).
# ⓐ ⓑ 는 환경(envs/practice) 전체를, ⓒ ⓓ ⓔ 는 모듈을 계획한다.

# ⓐ 아무 변수도 주지 않으면 compute 가 없다.
run "compute_block_default_has_no_compute" {
  command = plan

  assert {
    condition     = length(module.compute) == 0 && output.alb_dns_name == null && output.ecs_cluster_name == null
    error_message = "기본값에서 compute 모듈이 만들어진다. enable_compute 의 기본은 false 다."
  }
}

# ⓑ compute 를 켠 채로 ALB 를 인터넷 전체(0.0.0.0/0)에 열면 계획이 서지 않는다.
run "compute_block_rejects_open_cidr" {
  command = plan

  variables {
    enable_compute      = true
    alb_ingress_cidr    = "0.0.0.0/0"
    alb_certificate_arn = "arn:aws:acm:ap-northeast-2:000000000000:certificate/00000000-0000-0000-0000-000000000000"
  }

  expect_failures = [var.alb_ingress_cidr]
}

# ⓒ 인증서 없이 켜면 443 리스너의 precondition 이 막는다.
run "compute_block_rejects_missing_certificate" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  variables {
    certificate_arn = null
  }

  expect_failures = [aws_lb_listener.https]
}

# ⓓ 80 리스너는 443 으로 돌려보내기만 한다(대상 그룹으로 넘기지 않는다).
run "compute_block_http_listener_only_redirects" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  assert {
    condition = (
      aws_lb_listener.http.port == 80 && aws_lb_listener.http.protocol == "HTTP" &&
      length(aws_lb_listener.http.default_action) == 1 &&
      aws_lb_listener.http.default_action[0].type == "redirect" &&
      aws_lb_listener.http.default_action[0].target_group_arn == null &&
      aws_lb_listener.http.default_action[0].redirect[0].protocol == "HTTPS" &&
      aws_lb_listener.http.default_action[0].redirect[0].port == "443" &&
      aws_lb_listener.http.default_action[0].redirect[0].status_code == "HTTP_301"
    )
    error_message = "80 리스너가 443(HTTPS)으로 돌려보내기만 하지 않는다."
  }
}

# ⓔ 443 리스너는 HTTPS 이고, 받은 인증서와 고정한 TLS 정책을 쓴다.
run "compute_block_https_listener_uses_certificate" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  assert {
    condition = (
      aws_lb_listener.https.port == 443 && aws_lb_listener.https.protocol == "HTTPS" &&
      aws_lb_listener.https.certificate_arn == var.certificate_arn &&
      aws_lb_listener.https.ssl_policy == "ELBSecurityPolicy-TLS13-1-2-2021-06"
    )
    error_message = "443 리스너가 HTTPS·받은 인증서·고정한 TLS 정책이 아니다."
  }
}
