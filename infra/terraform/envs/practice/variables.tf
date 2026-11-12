# 이 환경에서 바꿀 수 있는 값. 내 값은 terraform.tfvars 에 적는다(terraform.tfvars.example 을 복사. git 에 넣지 않는다).

variable "region" {
  description = "자원을 만들 리전. ap-northeast-2 는 서울."
  type        = string
  default     = "ap-northeast-2"
}

variable "availability_zones" {
  description = "쓸 가용 영역 둘. 리전을 바꾸면 같이 바꾼다."
  type        = list(string)
  default     = ["ap-northeast-2a", "ap-northeast-2c"]
}

variable "project" {
  description = "자원 이름과 꼬리표에 쓰는 프로젝트 이름"
  type        = string
  default     = "esg-app"
}

variable "environment" {
  description = "환경 이름. 지금은 practice 하나뿐이다."
  type        = string
  default     = "practice"
}

# ── 켜고 끄는 것 ─────────────────────────────────────────────────────────────

variable "enable_nat_gateway" {
  description = "false(기본): 컨테이너를 공개 서브넷에 + 공인 IP. true: 사설 서브넷에 + NAT 게이트웨이(요금이 든다)."
  type        = bool
  default     = false
}

variable "enable_queue_redis" {
  description = "큐용 Redis(ElastiCache)를 만드는가. 큐가 다른 것(SQS 등)으로 바뀌면 끈다."
  type        = bool
  default     = true
}

variable "enable_database" {
  description = "Aurora PostgreSQL 을 만드는가"
  type        = bool
  default     = true
}

# ★ compute 모듈은 TS 서버(node dist/api.js) 기준이라 api-py 로 다시 쓸 때까지 켜지 않는다 — sid:MARC-ISSUE-108
variable "enable_compute" {
  description = "ECS 클러스터·ALB·서비스를 만드는가. 기본 false: 모듈이 TS 서버 기준이라 api-py 로 다시 쓸 때까지 켜지 않는다(sid:MARC-ISSUE-108). 켜려면 alb_ingress_cidr 를 좁히고 alb_certificate_arn 을 준다."
  type        = bool
  default     = false
}

variable "enable_frontend_bucket" {
  description = "정적 프론트용 버킷(자리만)을 만드는가"
  type        = bool
  default     = false
}

# ── 그 밖의 값 ───────────────────────────────────────────────────────────────

variable "image_tag" {
  description = "ECR 에 올린 이미지의 태그. 커밋마다 다른 값(예: git 커밋 해시 앞 7자)을 쓴다. server 와 parser 가 같은 태그를 쓴다."
  type        = string
  default     = "initial"
}

variable "cpu_architecture" {
  description = "이미지를 만든 CPU 종류. ARM64 또는 X86_64."
  type        = string
  default     = "ARM64"
}

variable "alb_ingress_cidr" {
  description = "ALB 에 들어올 수 있는 주소 범위(IPv4 CIDR). 기본은 아무도 들이지 않는 자리표시(문서용 주소 192.0.2.1/32)다. compute 를 켤 때 내 IP/32 처럼 좁은 범위를 준다. compute 를 켠 채로 /0(0.0.0.0/0·::/0)이면 계획 단계에서 실패한다."
  type        = string
  default     = "192.0.2.1/32"

  validation {
    condition     = can(cidrhost(var.alb_ingress_cidr, 0))
    error_message = "alb_ingress_cidr 가 CIDR 꼴(예: 203.0.113.7/32)이 아니다."
  }

  # 변수끼리 교차 검사(Terraform 1.9 부터): compute 를 켰을 때만 넓은 범위를 막는다.
  validation {
    condition     = !var.enable_compute || !(contains(["0.0.0.0/0", "::/0"], var.alb_ingress_cidr) || endswith(var.alb_ingress_cidr, "/0"))
    error_message = "compute 를 켠 채로 alb_ingress_cidr 가 /0(인터넷 전체)이다. 내 IP/32 처럼 좁힌다."
  }
}

variable "alb_certificate_arn" {
  description = "ALB 443 HTTPS 리스너에 붙일 ACM 인증서의 ARN. compute 를 켤 때 필수다(없으면 계획 단계에서 실패한다). 80 은 443 으로 돌려보내기만 한다."
  type        = string
  default     = null

  validation {
    condition     = !var.enable_compute || var.alb_certificate_arn != null
    error_message = "compute 를 켰는데 alb_certificate_arn 이 없다. ALB 는 HTTPS(443)로만 받는다."
  }
}

variable "cors_allowed_origins" {
  description = "브라우저에서 업로드 버킷에 직접 올릴 화면의 주소들. 비우면 CORS 규칙이 없다."
  type        = list(string)
  default     = []
}

variable "log_retention_days" {
  description = "컨테이너 기록을 며칠 보관하는가"
  type        = number
  default     = 30
}

variable "disposable" {
  description = "true 면 destroy 가 깨끗이 끝나게 한다: 파일이 든 버킷, 이미지가 든 저장소도 지운다. 연습 환경이라 기본이 true 다. 지키고 싶은 데이터가 생기면 false."
  type        = bool
  default     = true
}
