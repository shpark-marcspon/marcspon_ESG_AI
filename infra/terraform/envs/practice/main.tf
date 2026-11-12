# ─────────────────────────────────────────────────────────────────────────────
# envs/practice: 모듈 여덟을 엮어 연습용 환경 하나를 만든다.
#
# 읽는 법: 위에서 아래로, "남는 것 다섯 → 달라지는 것 셋". 모듈 사이를 오가는 값(module.x.y)을 따라가면
# 무엇이 무엇에 기대는지 보인다. Terraform 은 이 기댐을 보고 만드는 순서를 스스로 정한다.
#
#   network ──┬──────────────► queue_redis ──┐
#             ├──────────────► database ─────┤
#   storage ──┼─► iam ───────────────────────┼─► compute
#   registry ─┤    ▲                         │
#   logs ─────┴────┘─────────────────────────┘
# ─────────────────────────────────────────────────────────────────────────────

locals {
  # 자원 이름 앞에 붙는 말. 예: esg-app-practice
  name = "${var.project}-${var.environment}"
}

# ══ 스택이 바뀌어도 남는 것 ══════════════════════════════════════════════════

module "network" {
  source = "../../modules/network"

  name               = local.name
  availability_zones = var.availability_zones
  enable_nat_gateway = var.enable_nat_gateway
  alb_ingress_cidr   = var.alb_ingress_cidr
  # compute 의 ALB 는 HTTPS(443)로만 받는다. compute 를 켜면 ALB 보안 그룹에 443 도 연다.
  enable_https_ingress = var.enable_compute
}

module "storage" {
  source = "../../modules/storage"

  name                   = local.name
  cors_allowed_origins   = var.cors_allowed_origins
  force_destroy          = var.disposable
  enable_frontend_bucket = var.enable_frontend_bucket
}

module "registry" {
  source = "../../modules/registry"

  name         = local.name
  force_delete = var.disposable
}

module "logs" {
  source = "../../modules/logs"

  name              = local.name
  retention_in_days = var.log_retention_days
}

module "iam" {
  source = "../../modules/iam"

  name               = local.name
  uploads_bucket_arn = module.storage.uploads_bucket_arn
  ecr_repository_arns = [
    module.registry.server_repository_arn,
    module.registry.parser_repository_arn,
  ]
  log_group_arns = module.logs.log_group_arns

  # 실행 역할이 읽을 수 있는 비밀은 이 둘뿐이다. database 를 끄면 비밀도 없으므로 빈 목록이 된다.
  secret_arns = var.enable_database ? [
    module.database[0].database_url_secret_arn,
    module.database[0].migrate_database_url_secret_arn,
  ] : []
}

# ══ 스택에 따라 달라지는 것 (각각 변수로 끈다) ═══════════════════════════════
# count 가 붙은 모듈은 목록이 된다. 그래서 켜져 있을 때 module.database[0] 처럼 [0] 으로 가리킨다.

module "queue_redis" {
  source = "../../modules/queue_redis"
  count  = var.enable_queue_redis ? 1 : 0

  name              = local.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.network.redis_security_group_id
}

module "database" {
  source = "../../modules/database"
  count  = var.enable_database ? 1 : 0

  name              = local.name
  subnet_ids        = module.network.private_subnet_ids
  security_group_id = module.network.database_security_group_id
}

module "compute" {
  source = "../../modules/compute"
  count  = var.enable_compute ? 1 : 0

  name   = local.name
  region = var.region

  vpc_id                   = module.network.vpc_id
  public_subnet_ids        = module.network.public_subnet_ids
  task_subnet_ids          = module.network.task_subnet_ids
  assign_public_ip         = module.network.task_assign_public_ip
  alb_security_group_id    = module.network.alb_security_group_id
  api_security_group_id    = module.network.api_security_group_id
  worker_security_group_id = module.network.worker_security_group_id

  execution_role_arn   = module.iam.execution_role_arn
  api_task_role_arn    = module.iam.api_task_role_arn
  worker_task_role_arn = module.iam.worker_task_role_arn

  server_image     = "${module.registry.server_repository_url}:${var.image_tag}"
  parser_image     = "${module.registry.parser_repository_url}:${var.image_tag}"
  cpu_architecture = var.cpu_architecture

  api_log_group_name     = module.logs.api_log_group_name
  worker_log_group_name  = module.logs.worker_log_group_name
  parser_log_group_name  = module.logs.parser_log_group_name
  migrate_log_group_name = module.logs.migrate_log_group_name

  uploads_bucket_name = module.storage.uploads_bucket_name

  # 꺼진 모듈의 값은 null 로 넘긴다. compute 는 null 인 환경 변수를 넣지 않는다.
  redis_url                       = var.enable_queue_redis ? module.queue_redis[0].redis_url : null
  database_url_secret_arn         = var.enable_database ? module.database[0].database_url_secret_arn : null
  migrate_database_url_secret_arn = var.enable_database ? module.database[0].migrate_database_url_secret_arn : null

  certificate_arn = var.alb_certificate_arn
}
