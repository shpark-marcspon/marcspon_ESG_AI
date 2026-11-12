variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "region" {
  description = "리전. 컨테이너의 S3_REGION 과 기록을 보낼 리전에 쓴다."
  type        = string
}

# ── 네트워크 (network 모듈에서 온다) ─────────────────────────────────────────

variable "vpc_id" {
  description = "VPC 의 id"
  type        = string
}

variable "public_subnet_ids" {
  description = "ALB 를 둘 공개 서브넷 둘"
  type        = list(string)
}

variable "task_subnet_ids" {
  description = "태스크를 띄울 서브넷. NAT 를 켜면 사설, 끄면 공개(network 모듈이 골라 준다)."
  type        = list(string)
}

variable "assign_public_ip" {
  description = "태스크에 공인 IP 를 붙이는가. NAT 가 없으면 true 여야 이미지를 받을 수 있다."
  type        = bool
}

variable "alb_security_group_id" {
  description = "ALB 의 보안 그룹"
  type        = string
}

variable "api_security_group_id" {
  description = "api 태스크의 보안 그룹"
  type        = string
}

variable "worker_security_group_id" {
  description = "worker 태스크(와 migrate 태스크)의 보안 그룹"
  type        = string
}

variable "certificate_arn" {
  description = "ALB 443 HTTPS 리스너에 붙일 ACM 인증서의 ARN. 필수 — 없으면 계획 단계에서 실패한다(https 리스너의 precondition)."
  type        = string
  default     = null
}

# ── 역할 (iam 모듈에서 온다) ─────────────────────────────────────────────────

variable "execution_role_arn" {
  description = "실행 역할(이미지 받기, 비밀 넣기, 기록 쓰기)"
  type        = string
}

variable "api_task_role_arn" {
  description = "api 컨테이너 안의 코드가 쓰는 역할"
  type        = string
}

variable "worker_task_role_arn" {
  description = "worker·파서 컨테이너 안의 코드가 쓰는 역할"
  type        = string
}

# ── 이미지 (registry 모듈의 주소 + 태그) ─────────────────────────────────────

variable "server_image" {
  description = "server 이미지의 전체 주소(저장소 주소:태그). api, worker, migrate 가 같이 쓴다."
  type        = string
}

variable "parser_image" {
  description = "parser 이미지의 전체 주소(저장소 주소:태그)"
  type        = string
}

variable "cpu_architecture" {
  description = "이미지를 만든 CPU 종류. ARM64(애플 실리콘 맥에서 그냥 빌드하면 이것. Fargate 요금도 더 싸다) 또는 X86_64."
  type        = string
  default     = "ARM64"

  validation {
    condition     = contains(["ARM64", "X86_64"], var.cpu_architecture)
    error_message = "cpu_architecture 는 ARM64 또는 X86_64 다."
  }
}

# ── 기록 (logs 모듈에서 온다) ────────────────────────────────────────────────

variable "api_log_group_name" {
  description = "api 의 로그 그룹 이름"
  type        = string
}

variable "worker_log_group_name" {
  description = "worker 의 로그 그룹 이름"
  type        = string
}

variable "parser_log_group_name" {
  description = "파서의 로그 그룹 이름"
  type        = string
}

variable "migrate_log_group_name" {
  description = "migrate 의 로그 그룹 이름"
  type        = string
}

# ── 컨테이너에 넣어 줄 값 ────────────────────────────────────────────────────

variable "uploads_bucket_name" {
  description = "업로드 버킷의 이름 → S3_BUCKET"
  type        = string
}

variable "redis_url" {
  description = "Redis 의 주소 → REDIS_URL. queue_redis 모듈을 끄면 null 이고, 그러면 이 환경 변수를 넣지 않는다."
  type        = string
  default     = null
}

variable "database_url_secret_arn" {
  description = "DATABASE_URL 비밀의 ARN. database 모듈을 끄면 null 이고, 그러면 이 환경 변수를 넣지 않는다."
  type        = string
  default     = null
}

variable "migrate_database_url_secret_arn" {
  description = "MIGRATE_DATABASE_URL 비밀의 ARN. database 모듈을 끄면 null."
  type        = string
  default     = null
}

variable "parser_timeout_ms" {
  description = "worker 가 파서의 답을 기다리는 최대 시간 → PARSER_TIMEOUT_MS"
  type        = number
  default     = 30000
}

variable "queue_attempts" {
  description = "한 작업을 몇 번까지 시도하는가 → QUEUE_ATTEMPTS"
  type        = number
  default     = 3
}

variable "queue_backoff_ms" {
  description = "다시 시도 사이의 기본 대기 → QUEUE_BACKOFF_MS"
  type        = number
  default     = 1000
}

variable "worker_lock_ms" {
  description = "worker 가 죽었을 때 작업이 큐로 돌아오기까지의 시간 → WORKER_LOCK_MS"
  type        = number
  default     = 30000
}

# ── 크기와 수 ────────────────────────────────────────────────────────────────

variable "api_desired_count" {
  description = "api 태스크를 몇 벌 띄워 두는가"
  type        = number
  default     = 1
}

variable "worker_desired_count" {
  description = "worker 태스크를 몇 벌 띄워 두는가"
  type        = number
  default     = 1
}

variable "api_cpu" {
  description = "api 태스크의 CPU(1024 = vCPU 1개). Fargate 가 받는 조합만 된다: 256 이면 메모리 512/1024/2048."
  type        = number
  default     = 256
}

variable "api_memory" {
  description = "api 태스크의 메모리(MiB)"
  type        = number
  default     = 512
}

variable "worker_cpu" {
  description = "worker 태스크의 CPU. worker 와 파서 두 컨테이너가 나눠 쓴다. 512 면 메모리 1024~4096."
  type        = number
  default     = 512
}

variable "worker_memory" {
  description = "worker 태스크의 메모리(MiB). 두 컨테이너가 나눠 쓴다."
  type        = number
  default     = 1024
}

variable "api_stop_timeout_seconds" {
  description = "api 에 종료 신호(SIGTERM)를 보낸 뒤 강제로 죽이기까지 기다리는 시간. SHUTDOWN_TIMEOUT_MS(10초)보다 길게."
  type        = number
  default     = 15

  validation {
    condition     = var.api_stop_timeout_seconds <= 120
    error_message = "Fargate 의 stopTimeout 은 120초가 상한이다."
  }
}

variable "worker_stop_timeout_seconds" {
  description = "worker 에 종료 신호를 보낸 뒤 기다리는 시간. 하던 작업을 마칠 시간이다. SHUTDOWN_TIMEOUT_MS(40초)보다 길게."
  type        = number
  default     = 45

  validation {
    condition     = var.worker_stop_timeout_seconds <= 120
    error_message = "Fargate 의 stopTimeout 은 120초가 상한이다. 작업이 그보다 길어지면 조각 단위 저장과 이어 하기가 필요하다."
  }
}
