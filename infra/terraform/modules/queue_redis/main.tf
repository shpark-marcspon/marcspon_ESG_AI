# ─────────────────────────────────────────────────────────────────────────────
# queue_redis: 작업 큐가 쓰는 Redis(ElastiCache). compose 의 redis 에 대응한다.
#
# ★ 스택에 따라 버리는 모듈이다. 큐가 Redis 기반(BullMQ)일 때만 쓴다. SQS 로 가면 이 모듈을 끄고
#   (enable_queue_redis = false) SQS 큐와 그 권한을 적는 모듈을 새로 더한다.
#
# compose 와 달라지는 점 두 가지를 알고 써야 한다.
#   1. compose 는 `--appendonly yes` 로 디스크에 남긴다. ElastiCache 는 그 기능(AOF)을 지원하지 않는다.
#      노드가 하나면, 그 노드가 교체될 때 메모리에 있던 큐의 작업이 사라진다. 남기려면 node_count 를 2 이상으로.
#   2. "Serverless" 형은 쓰지 못한다. 메모리가 찼을 때의 정책을 바꿀 수 없기 때문이다(아래 noeviction).
# ─────────────────────────────────────────────────────────────────────────────

# 서브넷 그룹: "노드를 이 서브넷들 가운데 둔다"는 목록. 사설 서브넷만 준다 → 바깥에서 닿는 주소가 없다.
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.name}-redis"
  subnet_ids = var.subnet_ids
}

# 파라미터 그룹: redis.conf 에 해당하는 설정 묶음. 기본 그룹은 고칠 수 없어서 우리 것을 만든다.
resource "aws_elasticache_parameter_group" "main" {
  name        = "${var.name}-redis"
  family      = var.parameter_group_family
  description = "Queue use: never evict keys when memory is full"

  # ★ 이 모듈에서 가장 중요한 줄. ElastiCache 의 기본값은 volatile-lru(메모리가 차면 만료 시간이 있는 키부터 몰래 지운다)다.
  # 캐시에는 맞지만 큐에는 재앙이다: 지워진 키가 "처리해야 할 작업"일 수 있다.
  # noeviction 은 지우는 대신 쓰기를 거절한다 → 앱이 오류를 보고 알 수 있다. compose 의 --maxmemory-policy noeviction 과 같다.
  parameter {
    name  = "maxmemory-policy"
    value = "noeviction"
  }
}

# 복제 그룹: 주 노드 하나와 복제본들의 묶음. 노드가 하나여도 이 자원으로 만든다(암호화 설정이 여기에만 있다).
resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${var.name}-redis"
  description          = "Job queue for api and worker"

  engine               = var.engine
  engine_version       = var.engine_version
  node_type            = var.node_type
  port                 = 6379
  parameter_group_name = aws_elasticache_parameter_group.main.name

  # 노드 수. 2 이상일 때만 "주 노드가 죽으면 복제본이 이어받기"와 "두 가용 영역에 나눠 두기"를 켤 수 있다.
  num_cache_clusters         = var.node_count
  automatic_failover_enabled = var.node_count > 1
  multi_az_enabled           = var.node_count > 1

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [var.security_group_id]

  # 저장할 때와 오갈 때 모두 암호화한다. 오갈 때의 암호화(TLS)를 켜면 주소가 redis:// 가 아니라 rediss:// 가 된다.
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true

  # 설정을 바꾸면 다음 점검 시간까지 기다리지 않고 바로 적용한다(연습 환경에 맞춘 값. 운영에서는 false 를 생각한다).
  apply_immediately = true
}
