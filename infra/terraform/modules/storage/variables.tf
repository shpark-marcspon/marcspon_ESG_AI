variable "name" {
  description = "자원 이름 앞에 붙는 말"
  type        = string
}

variable "cors_allowed_origins" {
  description = "브라우저에서 이 버킷에 직접 올릴 수 있는 화면의 주소들. 예: [\"https://app.example.com\"]. 비우면 CORS 규칙을 만들지 않는다(브라우저에서 못 올린다. curl 은 된다)."
  type        = list(string)
  default     = []
}

variable "abort_incomplete_upload_days" {
  description = "올리다 만 조각(멀티파트 업로드)을 며칠 뒤에 지우는가"
  type        = number
  default     = 7
}

variable "force_destroy" {
  description = "true 면 destroy 때 버킷 안의 파일까지 지운다. 연습 환경에서만 true 로 둔다. false 면 파일이 든 버킷은 지워지지 않고 destroy 가 멈춘다."
  type        = bool
  default     = false
}

variable "enable_frontend_bucket" {
  description = "정적 프론트(React 빌드 결과)를 둘 버킷을 만드는가. 자리만 잡아 둔 것이라 기본은 끔."
  type        = bool
  default     = false
}
