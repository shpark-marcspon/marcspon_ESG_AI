variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "keep_image_count" {
  description = "저장소마다 남겨 둘 이미지의 수. 넘으면 오래된 것부터 지운다."
  type        = number
  default     = 20
}

variable "untagged_expire_days" {
  description = "태그가 없는 이미지를 며칠 뒤에 지우는가"
  type        = number
  default     = 7
}

variable "force_delete" {
  description = "true 면 destroy 때 이미지가 든 저장소도 지운다. 연습 환경에서만 true."
  type        = bool
  default     = false
}
