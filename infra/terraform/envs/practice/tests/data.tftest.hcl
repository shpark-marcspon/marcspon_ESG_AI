# Redis 와 Aurora: 큐로 쓰기에 맞는 설정인가, 비밀번호가 코드와 상태에 남지 않는 길인가. 그리고 ECR 과 로그 그룹.

mock_provider "aws" {
  override_during = plan
}

run "redis_never_evicts_and_is_private_and_encrypted" {
  command = plan

  module {
    source = "../../modules/queue_redis"
  }

  variables {
    name              = "test"
    subnet_ids        = ["subnet-private-a", "subnet-private-b"]
    security_group_id = "sg-redis"
  }

  # 메모리가 차도 키를 지우지 않는다(compose 의 --maxmemory-policy noeviction).
  assert {
    condition = [
      for p in aws_elasticache_parameter_group.main.parameter : p.value if p.name == "maxmemory-policy"
    ] == ["noeviction"]
    error_message = "Redis 의 maxmemory-policy 가 noeviction 이 아니다. 큐의 작업이 몰래 지워질 수 있다."
  }

  assert {
    condition     = aws_elasticache_replication_group.main.parameter_group_name == aws_elasticache_parameter_group.main.name
    error_message = "Redis 가 우리 파라미터 그룹을 쓰지 않는다(기본 그룹은 volatile-lru 다)."
  }

  assert {
    condition     = aws_elasticache_replication_group.main.at_rest_encryption_enabled == "true" && aws_elasticache_replication_group.main.transit_encryption_enabled == true
    error_message = "Redis 의 저장·전송 암호화 가운데 꺼진 것이 있다."
  }

  assert {
    condition     = aws_elasticache_replication_group.main.security_group_ids == toset(["sg-redis"]) && aws_elasticache_subnet_group.main.subnet_ids == toset(["subnet-private-a", "subnet-private-b"])
    error_message = "Redis 의 보안 그룹이나 서브넷이 넘겨받은 것과 다르다."
  }

  # 노드가 하나일 때는 자동 이어받기를 켤 수 없다.
  assert {
    condition     = aws_elasticache_replication_group.main.num_cache_clusters == 1 && aws_elasticache_replication_group.main.automatic_failover_enabled == false
    error_message = "기본값(노드 하나)에서 자동 이어받기가 켜져 있다."
  }
}

run "redis_fails_over_with_two_nodes" {
  command = plan

  module {
    source = "../../modules/queue_redis"
  }

  variables {
    name              = "test"
    subnet_ids        = ["subnet-private-a", "subnet-private-b"]
    security_group_id = "sg-redis"
    node_count        = 2
  }

  assert {
    condition     = aws_elasticache_replication_group.main.automatic_failover_enabled == true && aws_elasticache_replication_group.main.multi_az_enabled == true
    error_message = "노드가 둘인데 자동 이어받기나 가용 영역 분산이 꺼져 있다."
  }
}

run "database_is_private_encrypted_and_keeps_passwords_out_of_code" {
  command = plan

  module {
    source = "../../modules/database"
  }

  variables {
    name              = "test"
    subnet_ids        = ["subnet-private-a", "subnet-private-b"]
    security_group_id = "sg-database"
  }

  # 주 사용자의 비밀번호를 AWS 가 관리한다. 코드에서 비밀번호를 주지 않는다.
  assert {
    condition     = aws_rds_cluster.main.manage_master_user_password == true && aws_rds_cluster.main.master_password == null && aws_rds_cluster.main.master_password_wo == null
    error_message = "주 사용자의 비밀번호를 코드에서 주고 있다(상태 파일에 남는다). manage_master_user_password 를 쓴다."
  }

  assert {
    condition     = aws_rds_cluster.main.storage_encrypted == true
    error_message = "Aurora 의 저장 암호화가 꺼져 있다."
  }

  assert {
    condition     = aws_rds_cluster_instance.main.publicly_accessible == false && aws_rds_cluster.main.vpc_security_group_ids == toset(["sg-database"]) && aws_db_subnet_group.main.subnet_ids == toset(["subnet-private-a", "subnet-private-b"])
    error_message = "Aurora 가 공개돼 있거나 보안 그룹·서브넷이 넘겨받은 것과 다르다."
  }

  assert {
    condition     = aws_rds_cluster.main.engine == "aurora-postgresql" && aws_rds_cluster.main.engine_mode == "provisioned" && aws_rds_cluster_instance.main.instance_class == "db.serverless"
    error_message = "Aurora PostgreSQL Serverless v2 의 꼴(provisioned + db.serverless)이 아니다."
  }

  assert {
    condition     = aws_rds_cluster.main.serverlessv2_scaling_configuration[0].min_capacity == 0.5 && aws_rds_cluster.main.serverlessv2_scaling_configuration[0].max_capacity == 2
    error_message = "Aurora 의 크기 범위가 기본값(0.5~2 ACU)이 아니다."
  }
}

# ── 이미지 저장소와 기록 ─────────────────────────────────────────────────────

run "registry_tags_are_immutable_and_old_images_expire" {
  command = plan

  module {
    source = "../../modules/registry"
  }

  variables {
    name = "test"
  }

  assert {
    condition     = aws_ecr_repository.server.image_tag_mutability == "IMMUTABLE" && aws_ecr_repository.parser.image_tag_mutability == "IMMUTABLE"
    error_message = "ECR 저장소의 태그를 덮어쓸 수 있다(IMMUTABLE 이 아니다)."
  }

  assert {
    condition     = aws_ecr_repository.server.image_scanning_configuration[0].scan_on_push == true && aws_ecr_repository.parser.image_scanning_configuration[0].scan_on_push == true
    error_message = "ECR 저장소가 올릴 때 취약점을 훑지 않는다."
  }

  # 정리 규칙: 둘, 우선순위 1·2, 마지막 규칙이 "any"(ECR 의 요구), 전부 expire.
  assert {
    condition = (
      [for r in jsondecode(aws_ecr_lifecycle_policy.server.policy).rules : r.rulePriority] == [1, 2] &&
      [for r in jsondecode(aws_ecr_lifecycle_policy.server.policy).rules : r.selection.tagStatus] == ["untagged", "any"] &&
      alltrue([for r in jsondecode(aws_ecr_lifecycle_policy.server.policy).rules : r.action.type == "expire"]) &&
      aws_ecr_lifecycle_policy.parser.policy == aws_ecr_lifecycle_policy.server.policy
    )
    error_message = "ECR 정리 규칙의 꼴이 다르다(태그 없는 것 → 그 밖의 것 순서, 두 저장소가 같은 규칙)."
  }

  # 기본값에서는 이미지가 든 저장소를 지우지 못한다.
  assert {
    condition     = aws_ecr_repository.server.force_delete == false && aws_ecr_repository.parser.force_delete == false
    error_message = "기본값인데 이미지가 든 저장소를 지울 수 있다."
  }
}

run "log_groups_have_a_retention_period" {
  command = plan

  module {
    source = "../../modules/logs"
  }

  variables {
    name = "test"
  }

  assert {
    condition = alltrue([
      for g in [aws_cloudwatch_log_group.api, aws_cloudwatch_log_group.worker, aws_cloudwatch_log_group.parser, aws_cloudwatch_log_group.migrate] :
      g.retention_in_days == 30
    ])
    error_message = "보관 기간이 없는(영원히 쌓이는) 로그 그룹이 있다."
  }

  assert {
    condition = [
      aws_cloudwatch_log_group.api.name, aws_cloudwatch_log_group.worker.name,
      aws_cloudwatch_log_group.parser.name, aws_cloudwatch_log_group.migrate.name,
    ] == ["/ecs/test/api", "/ecs/test/worker", "/ecs/test/parser", "/ecs/test/migrate"]
    error_message = "로그 그룹의 이름이 /ecs/<이름>/<컨테이너> 꼴이 아니다."
  }
}
