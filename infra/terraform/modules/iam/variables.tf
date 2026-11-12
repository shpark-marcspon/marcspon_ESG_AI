variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "uploads_bucket_arn" {
  description = "업로드 버킷의 ARN. 태스크 역할의 S3 권한이 이 버킷으로 한정된다."
  type        = string
}

variable "ecr_repository_arns" {
  description = "이미지를 받아 올 ECR 저장소들의 ARN"
  type        = list(string)
}

variable "log_group_arns" {
  description = "컨테이너가 기록을 쓸 로그 그룹들의 ARN"
  type        = list(string)
}

variable "secret_arns" {
  description = "컨테이너에 환경 변수로 넣어 줄 비밀들의 ARN(Secrets Manager). 비어 있으면 비밀 읽기 권한을 아예 주지 않는다."
  type        = list(string)
  default     = []
}
