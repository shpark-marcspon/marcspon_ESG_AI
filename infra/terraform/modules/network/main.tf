# ─────────────────────────────────────────────────────────────────────────────
# network: 자원들이 사는 사설 네트워크(VPC)와, 누가 누구에게 말을 걸 수 있는가(보안 그룹).
#
#   인터넷
#     │
#   [인터넷 게이트웨이]
#     │
#   공개 서브넷 a, b ── ALB, (NAT 를 끈 구성에서는) api·worker 컨테이너, (NAT 를 켠 구성에서는) NAT 게이트웨이
#     │
#   사설 서브넷 a, b ── Aurora, Redis, (NAT 를 켠 구성에서는) api·worker 컨테이너
#
# 스택(서버 틀, 큐의 종류)이 바뀌어도 이 모듈은 남는다.
# ─────────────────────────────────────────────────────────────────────────────

# VPC: AWS 안에 긋는 나만의 사설 네트워크. 아래의 모든 자원이 이 안에 들어간다.
resource "aws_vpc" "main" {
  cidr_block = var.vpc_cidr

  # 둘 다 켜야 VPC 안에서 Aurora·Redis 의 엔드포인트 이름(…rds.amazonaws.com)이 사설 IP 로 풀린다.
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.name}-vpc" }
}

# 인터넷 게이트웨이: VPC 와 인터넷 사이의 문. 이것이 있어야 "공개" 서브넷이 성립한다. 요금이 없다.
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.name}-igw" }
}

# ── 서브넷 ──────────────────────────────────────────────────────────────────
# 서브넷은 VPC 의 주소를 가용 영역마다 잘라 놓은 조각이다. "공개"와 "사설"의 차이는 서브넷 자체가 아니라
# 붙은 라우팅 테이블에 있다: 인터넷 게이트웨이로 가는 길(0.0.0.0/0 → igw)이 있으면 공개, 없으면 사설.
# cidrsubnet(범위, 8, n): /16 을 /24 로 자른 n 번째 조각. 10.20.0.0/16 → 10.20.n.0/24 (주소 256개).

resource "aws_subnet" "public_a" {
  vpc_id            = aws_vpc.main.id
  availability_zone = var.availability_zones[0]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 0)

  # 여기서 뜨는 것에 공인 IP 를 자동으로 붙이지 않는다. 필요한 것(ECS 태스크)만 스스로 달라고 한다(assign_public_ip).
  map_public_ip_on_launch = false

  tags = { Name = "${var.name}-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id            = aws_vpc.main.id
  availability_zone = var.availability_zones[1]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 1)

  map_public_ip_on_launch = false

  tags = { Name = "${var.name}-public-b" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  availability_zone = var.availability_zones[0]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 10)

  tags = { Name = "${var.name}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  availability_zone = var.availability_zones[1]
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 11)

  tags = { Name = "${var.name}-private-b" }
}

# ── 라우팅 ──────────────────────────────────────────────────────────────────
# 라우팅 테이블: "이 주소로 가는 짐은 어디로 보내라"의 목록. VPC 안끼리 가는 길(local)은 늘 들어 있다.

# 공개 서브넷용: 그 밖의 모든 주소(0.0.0.0/0)는 인터넷 게이트웨이로.
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.name}-public" }
}

resource "aws_route" "public_internet" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.main.id
}

# 연결(association): 라우팅 테이블은 만들기만 해서는 아무 일도 하지 않는다. "이 서브넷은 이 표를 따른다"고 이어 줘야 한다.
# 공개 서브넷 둘을 위의 표에 잇는다. 이 연결이 서브넷을 "공개"로 만든다.
resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# 사설 서브넷용: 기본은 바깥으로 가는 길이 없다(VPC 안끼리만). Aurora 와 Redis 는 이것으로 충분하다.
resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.name}-private" }
}

# 사설 서브넷 둘을 사설용 표에 잇는다. 잇지 않으면 VPC 의 기본 표를 따르게 되어, 무엇을 따르는지 코드에서 보이지 않는다.
resource "aws_route_table_association" "private_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "private_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.private.id
}

# ── NAT 게이트웨이 (변수로 켠다. 기본은 끔) ──────────────────────────────────
# 사설 서브넷의 컨테이너가 바깥(ECR 에서 이미지 받기, S3, LLM API)으로 "나가기만" 할 수 있게 해 주는 관문.
# 바깥에서 안으로는 못 들어온다. 켜 두는 시간만큼, 지나간 데이터만큼 요금이 든다(infra/README.md 의 요금 표).
# count = 조건 ? 1 : 0 은 "조건이 참일 때만 만든다"는 Terraform 의 관용 표현이다. 그래서 아래에서 [0] 으로 가리킨다.
#
# 하나만 둔다(가용 영역 a). 그 영역이 죽으면 사설 서브넷 b 의 컨테이너도 바깥으로 못 나간다.
# 영역마다 하나씩 두면 그 걱정이 없지만 요금이 두 배다.

# NAT 게이트웨이가 바깥에 보일 고정 공인 IP.
resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? 1 : 0

  domain = "vpc"

  tags = { Name = "${var.name}-nat" }
}

resource "aws_nat_gateway" "main" {
  count = var.enable_nat_gateway ? 1 : 0

  # NAT 게이트웨이 자신은 공개 서브넷에 있어야 한다(자기가 인터넷으로 나가야 하므로).
  subnet_id     = aws_subnet.public_a.id
  allocation_id = aws_eip.nat[0].id

  tags = { Name = "${var.name}-nat" }

  # 인터넷 게이트웨이가 VPC 에 붙은 뒤에 만들어야 한다. Terraform 이 스스로 알 수 없는 순서라 적어 준다.
  depends_on = [aws_internet_gateway.main]
}

# 사설 서브넷에서 바깥으로 가는 길을 NAT 게이트웨이로 낸다. 이 한 줄이 없으면 사설 서브넷은 갇혀 있다.
resource "aws_route" "private_nat" {
  count = var.enable_nat_gateway ? 1 : 0

  route_table_id         = aws_route_table.private.id
  destination_cidr_block = "0.0.0.0/0"
  nat_gateway_id         = aws_nat_gateway.main[0].id
}

# ── 보안 그룹 ────────────────────────────────────────────────────────────────
# 보안 그룹은 자원에 붙이는 방화벽이다. 규칙이 없으면 아무것도 못 들어오고(ingress) 못 나간다(egress).
# 응답은 규칙 없이도 돌아간다(상태를 기억한다). 그래서 "누가 먼저 말을 거는가"만 적으면 된다.
# 출처를 IP 범위가 아니라 "다른 보안 그룹"으로 적을 수 있다 → "api 의 보안 그룹이 붙은 것만 DB 에 들어온다".
#
#   인터넷 ─80→ [alb] ─3000→ [api] ─5432→ [database]
#                              └────6379→ [redis]
#                           [worker] ─5432→ [database],  ─6379→ [redis]     (worker 로 들어오는 길은 없다)
#
# 규칙은 보안 그룹 안에 적지 않고 규칙 하나를 자원 하나로 적는다(공급자 문서가 권하는 꼴).
# ★ database 와 redis 로 들어오는 규칙은 아래 넷이 전부여야 한다. verify.sh 가 *.tf 파일을 글로 읽어 규칙 자원의 수를 센다
#   (그 검사가 읽을 수 있는 꼴로만 적는다: 규칙 하나 = aws_vpc_security_group_ingress_rule 자원 하나).

# 로드밸런서(ALB)
resource "aws_security_group" "alb" {
  name        = "${var.name}-alb"
  description = "ALB: receives HTTP from outside, forwards to api only"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-alb" }
}

# 바깥 → ALB : 80(HTTP). 바깥에 열린 문은 이것(과 아래의 443)뿐이다.
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  description       = "HTTP from allowed range"
  cidr_ipv4         = var.alb_ingress_cidr
  ip_protocol       = "tcp"
  from_port         = 80
  to_port           = 80
}

# 바깥 → ALB : 443(HTTPS). 인증서를 붙일 때 켠다.
resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  count = var.enable_https_ingress ? 1 : 0

  security_group_id = aws_security_group.alb.id
  description       = "HTTPS from allowed range"
  cidr_ipv4         = var.alb_ingress_cidr
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
}

# ALB → api : ALB 가 나갈 수 있는 곳은 api 의 컨테이너 포트뿐이다(요청 넘기기와 상태 확인).
resource "aws_vpc_security_group_egress_rule" "alb_to_api" {
  security_group_id            = aws_security_group.alb.id
  description                  = "Forward and health-check to api"
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = var.api_container_port
  to_port                      = var.api_container_port
}

# api 컨테이너
resource "aws_security_group" "api" {
  name        = "${var.name}-api"
  description = "api tasks: reachable only from the ALB"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-api" }
}

# ALB → api : 공개 서브넷에 있고 공인 IP 가 붙어 있어도, 들어올 수 있는 것은 ALB 뿐이다.
resource "aws_vpc_security_group_ingress_rule" "api_from_alb" {
  security_group_id            = aws_security_group.api.id
  description                  = "From ALB only"
  referenced_security_group_id = aws_security_group.alb.id
  ip_protocol                  = "tcp"
  from_port                    = var.api_container_port
  to_port                      = var.api_container_port
}

# api → 어디든 : 이미지 받기(ECR), S3, Secrets Manager, CloudWatch Logs, DB, Redis 로 나간다.
# ip_protocol = "-1" 은 "모든 프로토콜·모든 포트". 나가는 쪽은 넓게 두고 들어오는 쪽을 좁힌다.
resource "aws_vpc_security_group_egress_rule" "api_all" {
  security_group_id = aws_security_group.api.id
  description       = "All outbound"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# worker 태스크(worker + 파서)
resource "aws_security_group" "worker" {
  name        = "${var.name}-worker"
  description = "worker tasks: no inbound at all"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-worker" }
}

# worker 로 들어오는 규칙은 일부러 하나도 없다. 일은 큐에서 꺼내 오고, 파서는 같은 태스크 안에서 localhost 로 만난다.

resource "aws_vpc_security_group_egress_rule" "worker_all" {
  security_group_id = aws_security_group.worker.id
  description       = "All outbound"
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}

# DB(Aurora)
resource "aws_security_group" "database" {
  name        = "${var.name}-database"
  description = "Aurora: reachable only from api and worker tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-database" }
}

resource "aws_vpc_security_group_ingress_rule" "database_from_api" {
  security_group_id            = aws_security_group.database.id
  description                  = "PostgreSQL from api"
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

# 한 번짜리 migrate 태스크는 사람이 run-task 로 띄울 때 worker 의 보안 그룹을 골라 단다(infra/README.md 의 차례 6).
# 그래서 migrate 용 규칙이 따로 없다.
resource "aws_vpc_security_group_ingress_rule" "database_from_worker" {
  security_group_id            = aws_security_group.database.id
  description                  = "PostgreSQL from worker"
  referenced_security_group_id = aws_security_group.worker.id
  ip_protocol                  = "tcp"
  from_port                    = 5432
  to_port                      = 5432
}

# 큐(Redis)
resource "aws_security_group" "redis" {
  name        = "${var.name}-redis"
  description = "Redis: reachable only from api and worker tasks"
  vpc_id      = aws_vpc.main.id

  tags = { Name = "${var.name}-redis" }
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_api" {
  security_group_id            = aws_security_group.redis.id
  description                  = "Redis from api"
  referenced_security_group_id = aws_security_group.api.id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_worker" {
  security_group_id            = aws_security_group.redis.id
  description                  = "Redis from worker"
  referenced_security_group_id = aws_security_group.worker.id
  ip_protocol                  = "tcp"
  from_port                    = 6379
  to_port                      = 6379
}

# database 와 redis 에는 나가는 규칙이 없다. 스스로 어디에 말을 걸 일이 없고, 받은 요청의 응답은 규칙 없이 돌아간다.
