variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "retention_in_days" {
  description = "기록을 며칠 보관하는가. 정해진 값만 된다(1, 3, 5, 7, 14, 30, 60, 90 …). 0 은 영원히."
  type        = number
  default     = 30
}
