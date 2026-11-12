variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "subnet_ids" {
  description = "Redis 노드를 둘 서브넷(사설 서브넷 둘)"
  type        = list(string)
}

variable "security_group_id" {
  description = "Redis 에 붙일 보안 그룹(network 모듈의 redis). api 와 worker 에서만 들어온다."
  type        = string
}

variable "engine" {
  description = "redis(Redis OSS) 또는 valkey(Redis 에서 갈라져 나온 호환 엔진. ElastiCache 에서 더 싸다). 바꾸면 engine_version 과 parameter_group_family 도 같이 바꾼다."
  type        = string
  default     = "redis"

  validation {
    condition     = contains(["redis", "valkey"], var.engine)
    error_message = "engine 은 redis 또는 valkey 다."
  }
}

variable "engine_version" {
  description = "엔진 버전. redis 는 7.1, valkey 는 8.2 같은 값."
  type        = string
  default     = "7.1"
}

variable "parameter_group_family" {
  description = "파라미터 그룹의 계열. 엔진과 큰 버전에 맞춘다: redis7, valkey7, valkey8, valkey9."
  type        = string
  default     = "redis7"
}

variable "node_type" {
  description = "노드 한 대의 크기. cache.t4g.micro 는 메모리 0.5GB 급의 가장 싼 축이다."
  type        = string
  default     = "cache.t4g.micro"
}

variable "node_count" {
  description = "노드 수(주 노드 1 + 복제본). 1 이면 그 노드가 바뀔 때 큐에 든 작업이 사라진다. 2 이상이면 복제본이 이어받는다."
  type        = number
  default     = 1
}
