variable "name" {
  description = "자원 이름 앞에 붙는 말. 예: esg-app-practice"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC 전체의 사설 주소 범위. /16 이면 주소가 65,536개다."
  type        = string
  default     = "10.20.0.0/16"
}

variable "availability_zones" {
  description = "쓸 가용 영역 둘. 가용 영역은 한 리전 안의 서로 떨어진 데이터센터 묶음이다. ALB 와 Aurora 의 서브넷 그룹이 둘 이상을 요구한다."
  type        = list(string)

  validation {
    condition     = length(var.availability_zones) == 2
    error_message = "가용 영역은 정확히 둘을 준다(이 모듈은 서브넷을 영역마다 하나씩, 풀어서 적었다)."
  }
}

variable "enable_nat_gateway" {
  description = <<-EOT
    false(기본): 컨테이너를 공개 서브넷에 두고 공인 IP 를 붙인다. 들어오는 길은 보안 그룹이 막는다. NAT 게이트웨이 요금이 없다.
    true: 컨테이너를 사설 서브넷에 두고, 바깥으로 나가는 길을 NAT 게이트웨이 하나로 낸다. 시간당 요금과 지나간 데이터만큼의 요금이 든다.
  EOT
  type        = bool
  default     = false
}

variable "api_container_port" {
  description = "api 컨테이너가 듣는 포트. ALB 가 이 포트로 넘긴다."
  type        = number
  default     = 3000
}

variable "alb_ingress_cidr" {
  description = "ALB 에 들어올 수 있는 주소 범위. 0.0.0.0/0 은 인터넷 전체다. 연습 중에는 내 집·사무실 IP/32 로 좁혀도 된다."
  type        = string
  default     = "0.0.0.0/0"
}

variable "enable_https_ingress" {
  description = "ALB 보안 그룹에 443 을 여는가. 인증서와 HTTPS 리스너를 붙일 때 같이 켠다(지금은 자리만)."
  type        = bool
  default     = false
}
