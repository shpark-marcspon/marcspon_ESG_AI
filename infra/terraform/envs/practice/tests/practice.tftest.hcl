# (바) 환경 전체: 끄는 변수를 뒤집어도 계획이 서고, 끈 모듈의 자원이 0 이다.
#
# 여기서는 환경(envs/practice)을 통째로 계획한다. 모듈 안의 자원은 직접 가리킬 수 없어서, 모듈의 수와 출력만 본다.
# "계획이 선다"는 것은 모듈 사이로 넘기는 값의 이름과 꼴이 맞는다는 뜻이다. 실제로 만들어진다는 뜻이 아니다.

mock_provider "aws" {}

run "defaults_plan_everything_without_nat" {
  command = plan

  # compute 는 기본으로 꺼져 있다(TS 서버 기준이라 api-py 로 다시 쓸 때까지 — sid:MARC-ISSUE-108).
  assert {
    condition     = length(module.queue_redis) == 1 && length(module.database) == 1 && length(module.compute) == 0
    error_message = "기본값에서 Redis, DB 가운데 꺼진 것이 있거나 compute 가 켜져 있다."
  }

  assert {
    condition     = output.nat_gateway_count == 0
    error_message = "기본값에서 NAT 게이트웨이가 만들어진다(돈이 든다). 기본은 끔이어야 한다."
  }
}

run "nat_on" {
  command = plan

  variables {
    enable_nat_gateway = true
  }

  assert {
    condition     = output.nat_gateway_count == 1
    error_message = "NAT 를 켰는데 NAT 게이트웨이가 하나가 아니다."
  }
}

run "redis_off" {
  command = plan

  variables {
    enable_queue_redis = false
  }

  assert {
    condition     = length(module.queue_redis) == 0 && output.redis_url == null
    error_message = "Redis 를 껐는데 Redis 모듈이나 그 출력이 남아 있다."
  }

  assert {
    condition     = length(module.database) == 1 && length(module.compute) == 0
    error_message = "Redis 를 끄자 DB 가 같이 꺼졌거나 compute 가 켜졌다."
  }
}

run "database_off" {
  command = plan

  variables {
    enable_database = false
  }

  assert {
    condition     = length(module.database) == 0 && output.database_endpoint == null && output.database_url_secret_arn == null && output.database_master_user_secret_arn == null
    error_message = "DB 를 껐는데 DB 모듈이나 그 출력이 남아 있다."
  }

  assert {
    condition     = length(module.queue_redis) == 1 && length(module.compute) == 0
    error_message = "DB 를 끄자 Redis 가 같이 꺼졌거나 compute 가 켜졌다."
  }
}

run "compute_off" {
  command = plan

  variables {
    enable_compute = false
  }

  assert {
    condition     = length(module.compute) == 0 && output.alb_dns_name == null && output.ecs_cluster_name == null
    error_message = "compute 를 껐는데 compute 모듈이나 그 출력이 남아 있다."
  }

  assert {
    condition     = length(module.queue_redis) == 1 && length(module.database) == 1
    error_message = "compute 를 끄자 다른 모듈이 같이 꺼졌다."
  }
}

run "everything_optional_off" {
  command = plan

  variables {
    enable_nat_gateway = false
    enable_queue_redis = false
    enable_database    = false
    enable_compute     = false
  }

  assert {
    condition     = length(module.queue_redis) == 0 && length(module.database) == 0 && length(module.compute) == 0 && output.nat_gateway_count == 0
    error_message = "전부 껐는데 남은 모듈이 있다."
  }
}

run "everything_on_with_nat" {
  command = plan

  variables {
    enable_nat_gateway     = true
    enable_queue_redis     = true
    enable_database        = true
    enable_compute         = true
    enable_frontend_bucket = true
    # compute 를 켜려면 둘 다 필수다: 좁은 주소 범위와 HTTPS 인증서.
    alb_ingress_cidr    = "203.0.113.7/32"
    alb_certificate_arn = "arn:aws:acm:ap-northeast-2:000000000000:certificate/00000000-0000-0000-0000-000000000000"
  }

  assert {
    condition     = length(module.queue_redis) == 1 && length(module.database) == 1 && length(module.compute) == 1 && output.nat_gateway_count == 1
    error_message = "전부 켰는데 빠진 모듈이 있다."
  }
}
