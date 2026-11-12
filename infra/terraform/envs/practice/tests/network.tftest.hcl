# (나) DB 와 Redis 의 보안 그룹: 들어오는 규칙의 출처가 api·worker 의 보안 그룹뿐이고 0.0.0.0/0 이 없다.
# (바) NAT 변수를 끄면 NAT 게이트웨이가 0, 켜면 1.
#
# ★ 이 테스트는 "아래에 이름을 적은 규칙"의 값만 본다. 누가 새 규칙 자원을 더하면 여기서는 보이지 않는다.
#   그 구멍은 verify.sh 의 「보안 그룹 규칙의 수」 검사가 막는다(보안 그룹마다 들어오는 규칙의 수를 센다).

mock_provider "aws" {
  override_during = plan
}

run "database_and_redis_accept_only_api_and_worker" {
  command = plan

  module {
    source = "../../modules/network"
  }

  variables {
    name               = "test"
    availability_zones = ["ap-northeast-2a", "ap-northeast-2c"]
  }

  # 보안 그룹마다 다른 가짜 id 를 준다. 그래야 "출처가 api 의 것인가 worker 의 것인가"를 가릴 수 있다.
  override_resource {
    target          = aws_security_group.alb
    override_during = plan
    values          = { id = "sg-alb" }
  }
  override_resource {
    target          = aws_security_group.api
    override_during = plan
    values          = { id = "sg-api" }
  }
  override_resource {
    target          = aws_security_group.worker
    override_during = plan
    values          = { id = "sg-worker" }
  }
  override_resource {
    target          = aws_security_group.database
    override_during = plan
    values          = { id = "sg-database" }
  }
  override_resource {
    target          = aws_security_group.redis
    override_during = plan
    values          = { id = "sg-redis" }
  }

  # ── DB ──
  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.database_from_api.security_group_id == "sg-database" &&
      aws_vpc_security_group_ingress_rule.database_from_api.referenced_security_group_id == "sg-api" &&
      aws_vpc_security_group_ingress_rule.database_from_api.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.database_from_api.cidr_ipv6 == null &&
      aws_vpc_security_group_ingress_rule.database_from_api.prefix_list_id == null
    )
    error_message = "DB 로 들어오는 규칙(api 쪽)의 출처가 api 의 보안 그룹이 아니거나 IP 범위로 열려 있다."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.database_from_worker.security_group_id == "sg-database" &&
      aws_vpc_security_group_ingress_rule.database_from_worker.referenced_security_group_id == "sg-worker" &&
      aws_vpc_security_group_ingress_rule.database_from_worker.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.database_from_worker.cidr_ipv6 == null &&
      aws_vpc_security_group_ingress_rule.database_from_worker.prefix_list_id == null
    )
    error_message = "DB 로 들어오는 규칙(worker 쪽)의 출처가 worker 의 보안 그룹이 아니거나 IP 범위로 열려 있다."
  }

  assert {
    condition = alltrue([
      aws_vpc_security_group_ingress_rule.database_from_api.ip_protocol == "tcp",
      aws_vpc_security_group_ingress_rule.database_from_api.from_port == 5432,
      aws_vpc_security_group_ingress_rule.database_from_api.to_port == 5432,
      aws_vpc_security_group_ingress_rule.database_from_worker.ip_protocol == "tcp",
      aws_vpc_security_group_ingress_rule.database_from_worker.from_port == 5432,
      aws_vpc_security_group_ingress_rule.database_from_worker.to_port == 5432,
    ])
    error_message = "DB 로 들어오는 규칙이 5432/tcp 하나로 좁혀져 있지 않다."
  }

  # ── Redis ──
  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.redis_from_api.security_group_id == "sg-redis" &&
      aws_vpc_security_group_ingress_rule.redis_from_api.referenced_security_group_id == "sg-api" &&
      aws_vpc_security_group_ingress_rule.redis_from_api.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.redis_from_api.cidr_ipv6 == null &&
      aws_vpc_security_group_ingress_rule.redis_from_api.prefix_list_id == null
    )
    error_message = "Redis 로 들어오는 규칙(api 쪽)의 출처가 api 의 보안 그룹이 아니거나 IP 범위로 열려 있다."
  }

  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.redis_from_worker.security_group_id == "sg-redis" &&
      aws_vpc_security_group_ingress_rule.redis_from_worker.referenced_security_group_id == "sg-worker" &&
      aws_vpc_security_group_ingress_rule.redis_from_worker.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.redis_from_worker.cidr_ipv6 == null &&
      aws_vpc_security_group_ingress_rule.redis_from_worker.prefix_list_id == null
    )
    error_message = "Redis 로 들어오는 규칙(worker 쪽)의 출처가 worker 의 보안 그룹이 아니거나 IP 범위로 열려 있다."
  }

  assert {
    condition = alltrue([
      aws_vpc_security_group_ingress_rule.redis_from_api.ip_protocol == "tcp",
      aws_vpc_security_group_ingress_rule.redis_from_api.from_port == 6379,
      aws_vpc_security_group_ingress_rule.redis_from_api.to_port == 6379,
      aws_vpc_security_group_ingress_rule.redis_from_worker.ip_protocol == "tcp",
      aws_vpc_security_group_ingress_rule.redis_from_worker.from_port == 6379,
      aws_vpc_security_group_ingress_rule.redis_from_worker.to_port == 6379,
    ])
    error_message = "Redis 로 들어오는 규칙이 6379/tcp 하나로 좁혀져 있지 않다."
  }

  # ── api: ALB 에서만, 컨테이너 포트 하나로 ──
  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.api_from_alb.security_group_id == "sg-api" &&
      aws_vpc_security_group_ingress_rule.api_from_alb.referenced_security_group_id == "sg-alb" &&
      aws_vpc_security_group_ingress_rule.api_from_alb.cidr_ipv4 == null &&
      aws_vpc_security_group_ingress_rule.api_from_alb.from_port == 3000 &&
      aws_vpc_security_group_ingress_rule.api_from_alb.to_port == 3000
    )
    error_message = "api 로 들어오는 규칙의 출처가 ALB 의 보안 그룹이 아니거나 포트가 3000 이 아니다."
  }

  # ── ALB: 바깥에 여는 것은 80 뿐(기본값) ──
  assert {
    condition = (
      aws_vpc_security_group_ingress_rule.alb_http.security_group_id == "sg-alb" &&
      aws_vpc_security_group_ingress_rule.alb_http.from_port == 80 &&
      aws_vpc_security_group_ingress_rule.alb_http.to_port == 80 &&
      length(aws_vpc_security_group_ingress_rule.alb_https) == 0
    )
    error_message = "ALB 가 바깥에 여는 포트가 80 하나가 아니다."
  }

  # 서브넷에서 뜨는 것에 공인 IP 를 자동으로 붙이지 않는다.
  assert {
    condition     = aws_subnet.public_a.map_public_ip_on_launch == false && aws_subnet.public_b.map_public_ip_on_launch == false
    error_message = "공개 서브넷이 공인 IP 를 자동으로 붙인다."
  }
}

run "nat_off_means_no_nat_gateway_and_public_tasks" {
  command = plan

  module {
    source = "../../modules/network"
  }

  variables {
    name               = "test"
    availability_zones = ["ap-northeast-2a", "ap-northeast-2c"]
    enable_nat_gateway = false
  }

  override_resource {
    target          = aws_subnet.public_a
    override_during = plan
    values          = { id = "subnet-public-a" }
  }
  override_resource {
    target          = aws_subnet.public_b
    override_during = plan
    values          = { id = "subnet-public-b" }
  }
  override_resource {
    target          = aws_subnet.private_a
    override_during = plan
    values          = { id = "subnet-private-a" }
  }
  override_resource {
    target          = aws_subnet.private_b
    override_during = plan
    values          = { id = "subnet-private-b" }
  }

  assert {
    condition     = length(aws_nat_gateway.main) == 0 && length(aws_eip.nat) == 0 && length(aws_route.private_nat) == 0
    error_message = "NAT 를 껐는데 NAT 게이트웨이, 그 공인 IP, 또는 NAT 로 가는 길이 만들어진다."
  }

  assert {
    condition     = output.nat_gateway_count == 0 && output.task_assign_public_ip == true
    error_message = "NAT 를 끈 구성에서는 태스크에 공인 IP 를 붙여야 한다(그래야 이미지를 받는다)."
  }

  assert {
    condition     = output.task_subnet_ids == ["subnet-public-a", "subnet-public-b"]
    error_message = "NAT 를 끈 구성에서는 태스크가 공개 서브넷에 떠야 한다."
  }
}

run "nat_on_means_one_nat_gateway_and_private_tasks" {
  command = plan

  module {
    source = "../../modules/network"
  }

  variables {
    name               = "test"
    availability_zones = ["ap-northeast-2a", "ap-northeast-2c"]
    enable_nat_gateway = true
  }

  override_resource {
    target          = aws_subnet.public_a
    override_during = plan
    values          = { id = "subnet-public-a" }
  }
  override_resource {
    target          = aws_subnet.public_b
    override_during = plan
    values          = { id = "subnet-public-b" }
  }
  override_resource {
    target          = aws_subnet.private_a
    override_during = plan
    values          = { id = "subnet-private-a" }
  }
  override_resource {
    target          = aws_subnet.private_b
    override_during = plan
    values          = { id = "subnet-private-b" }
  }

  assert {
    condition     = length(aws_nat_gateway.main) == 1 && length(aws_eip.nat) == 1 && length(aws_route.private_nat) == 1
    error_message = "NAT 를 켰는데 NAT 게이트웨이, 그 공인 IP, NAT 로 가는 길 가운데 빠진 것이 있다."
  }

  assert {
    condition     = aws_nat_gateway.main[0].subnet_id == "subnet-public-a" && aws_route.private_nat[0].destination_cidr_block == "0.0.0.0/0"
    error_message = "NAT 게이트웨이가 공개 서브넷에 있지 않거나, 사설 서브넷의 바깥 길이 0.0.0.0/0 이 아니다."
  }

  assert {
    condition     = output.nat_gateway_count == 1 && output.task_assign_public_ip == false
    error_message = "NAT 를 켠 구성에서는 태스크에 공인 IP 를 붙이지 않는다."
  }

  assert {
    condition     = output.task_subnet_ids == ["subnet-private-a", "subnet-private-b"]
    error_message = "NAT 를 켠 구성에서는 태스크가 사설 서브넷에 떠야 한다."
  }
}
