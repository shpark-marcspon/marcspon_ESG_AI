# ─────────────────────────────────────────────────────────────────────────────
# database: Aurora PostgreSQL(Serverless v2). compose 의 postgres 에 대응한다.
#
# ★ 스택에 따라 달라질 수 있는 모듈이다(크기, 형태). 끄려면 enable_database = false.
#
# Aurora 는 자원이 둘로 나뉜다.
#   클러스터(aws_rds_cluster)           : 데이터가 사는 곳(저장소), 접속 주소, 사용자, 백업
#   인스턴스(aws_rds_cluster_instance)  : 그 데이터를 읽고 쓰는 컴퓨터. 하나 이상 있어야 접속할 수 있다
#
# 비밀번호를 다루는 길(이 모듈의 핵심):
#   ① 주 사용자의 비밀번호: 우리가 정하지 않는다. AWS 가 만들어 Secrets Manager 에 넣고 주기적으로 바꾼다
#      (manage_master_user_password). Terraform 의 코드에도 상태 파일에도 비밀번호가 없다.
#   ② 앱이 쓰는 접속 주소(DATABASE_URL, MIGRATE_DATABASE_URL): 비밀번호가 든 한 줄이라 통째로 비밀이다.
#      Terraform 은 "빈 비밀 그릇"만 만들고, 값은 사람이 한 번 넣는다(infra/README.md 의 처음 적용하는 차례).
#      값이 Terraform 을 지나가지 않으므로 상태 파일에 남지 않는다.
#   하지 않은 길: 변수로 비밀번호를 받아 master_password 에 넣기. 값이 상태 파일에 평문으로 남는다.
# ─────────────────────────────────────────────────────────────────────────────

# 서브넷 그룹: "DB 를 이 서브넷들 가운데 둔다". 서로 다른 가용 영역의 서브넷이 둘 이상이어야 한다.
resource "aws_db_subnet_group" "main" {
  name       = "${var.name}-database"
  subnet_ids = var.subnet_ids
}

# 클러스터: 데이터가 사는 곳과 접속 주소. 엔진, 사용자, 암호화, 크기 범위, 백업을 여기서 정한다.
resource "aws_rds_cluster" "main" {
  cluster_identifier = "${var.name}-database"

  engine         = "aurora-postgresql"
  engine_version = var.engine_version
  # Serverless v2 는 이름과 달리 engine_mode 가 "provisioned" 다(serverless 는 옛 v1 을 가리킨다).
  engine_mode = "provisioned"

  database_name   = var.database_name
  master_username = var.master_username
  # ① 비밀번호를 AWS 가 만들고 보관한다. 만들어진 비밀의 위치는 출력 master_user_secret_arn 에 나온다.
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.security_group_id]

  # 저장할 때의 암호화. Serverless v2 는 적지 않으면 꺼진 채로 만들어지고, 만든 뒤에는 켤 수 없다.
  storage_encrypted = true

  # 크기를 스스로 늘리고 줄이는 범위. 요금은 쓰고 있는 ACU × 시간이다.
  serverlessv2_scaling_configuration {
    min_capacity             = var.min_capacity
    max_capacity             = var.max_capacity
    seconds_until_auto_pause = var.min_capacity == 0 ? var.seconds_until_auto_pause : null
  }

  enable_http_endpoint = var.enable_data_api

  backup_retention_period = var.backup_retention_days

  deletion_protection = var.deletion_protection
  skip_final_snapshot = var.skip_final_snapshot
  # 마지막 스냅샷을 남기는 설정이면 이 이름으로 남긴다.
  final_snapshot_identifier = var.skip_final_snapshot ? null : "${var.name}-database-final"
}

# 인스턴스 하나. db.serverless = "크기는 위의 범위 안에서 스스로". 운영에서 장애에 대비하려면 다른 가용 영역에 하나 더 둔다.
resource "aws_rds_cluster_instance" "main" {
  identifier         = "${var.name}-database-1"
  cluster_identifier = aws_rds_cluster.main.id

  engine         = aws_rds_cluster.main.engine
  engine_version = aws_rds_cluster.main.engine_version
  instance_class = "db.serverless"

  # 공인 주소를 주지 않는다. VPC 안에서만 닿는다.
  publicly_accessible = false
}

# ② 앱 역할(esg_app)의 접속 주소를 담을 그릇. api 와 worker 의 DATABASE_URL 이 된다.
# 값(postgres://esg_app:<비밀번호>@<주소>:5432/esg?sslmode=require)은 여기서 넣지 않는다.
# Aurora PostgreSQL 17 은 암호화된 연결(TLS)만 받는 것이 기본이라 주소에 sslmode 가 붙는다.
resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.name}/database-url"
  description             = "DATABASE_URL for api and worker (app role, cannot bypass RLS). Value is set by hand."
  recovery_window_in_days = var.secret_recovery_window_days
}

# ② 주인 역할(테이블을 만들고 바꾸는 역할)의 접속 주소를 담을 그릇. migrate 태스크의 MIGRATE_DATABASE_URL 이 된다.
# api 와 worker 의 태스크 정의는 이 비밀을 가리키지 않는다.
resource "aws_secretsmanager_secret" "migrate_database_url" {
  name                    = "${var.name}/migrate-database-url"
  description             = "MIGRATE_DATABASE_URL for the one-off migrate task (owner role). Value is set by hand."
  recovery_window_in_days = var.secret_recovery_window_days
}
