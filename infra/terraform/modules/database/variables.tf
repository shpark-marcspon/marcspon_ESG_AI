variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "subnet_ids" {
  description = "DB 를 둘 서브넷(서로 다른 가용 영역의 사설 서브넷 둘)"
  type        = list(string)
}

variable "security_group_id" {
  description = "DB 에 붙일 보안 그룹(network 모듈의 database). api 와 worker 에서만 들어온다."
  type        = string
}

variable "engine_version" {
  description = "Aurora PostgreSQL 의 버전. compose 의 postgres 와 큰 버전(17)을 맞춘다. 그 리전에서 고를 수 있는 값이어야 한다."
  type        = string
  default     = "17.7"
}

variable "database_name" {
  description = "처음 만들어 둘 데이터베이스 이름. compose 의 POSTGRES_DB 와 같다."
  type        = string
  default     = "esg"
}

variable "master_username" {
  description = "주 사용자(관리자)의 이름. 사람이 처음 한 번 역할을 만들 때만 쓴다. 앱도 마이그레이션도 이 사용자를 쓰지 않는다."
  type        = string
  default     = "esg_admin"
}

variable "min_capacity" {
  description = "가장 한가할 때의 크기(ACU. 1 ACU 는 메모리 약 2GB). 0 이면 쓰지 않을 때 멈추지만, api 의 /readyz 가 계속 DB 를 두드리므로 api 가 떠 있는 동안에는 멈추지 않는다."
  type        = number
  default     = 0.5
}

variable "max_capacity" {
  description = "가장 바쁠 때의 크기(ACU). 요금의 상한을 정하는 값이기도 하다."
  type        = number
  default     = 2
}

variable "seconds_until_auto_pause" {
  description = "min_capacity 가 0 일 때, 연결이 없은 지 몇 초 뒤에 멈추는가(300~86400)"
  type        = number
  default     = 300
}

variable "enable_data_api" {
  description = "Data API(HTTPS 로 SQL 을 보내는 길)를 켠다. 콘솔의 쿼리 편집기에서 관리형 비밀로 SQL 을 돌릴 수 있어, 사설 서브넷의 DB 에 처음 역할을 만들 때 쓴다."
  type        = bool
  default     = true
}

variable "deletion_protection" {
  description = "true 면 DB 를 지우지 못한다(destroy 가 멈춘다). 운영에서는 true."
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "true 면 지울 때 마지막 스냅샷을 남기지 않는다. 연습 환경에서만 true."
  type        = bool
  default     = true
}

variable "backup_retention_days" {
  description = "자동 백업을 며칠 보관하는가(1~35)"
  type        = number
  default     = 1
}

variable "secret_recovery_window_days" {
  description = "비밀을 지웠을 때 되살릴 수 있는 기간. 0 이면 바로 지운다(같은 이름으로 곧바로 다시 만들 수 있다. 연습용). 운영에서는 7~30."
  type        = number
  default     = 0
}
