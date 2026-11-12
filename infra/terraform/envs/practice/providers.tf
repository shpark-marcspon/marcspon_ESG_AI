# 공급자 설정: 어느 리전에 만들 것인가. 자격 증명은 여기에 적지 않는다.
# (적용할 때 Terraform 이 환경 변수나 ~/.aws 의 프로필에서 스스로 찾는다. infra/README.md 참고)
provider "aws" {
  region = var.region

  # 이 코드가 만드는 모든 자원에 같은 꼬리표를 붙인다. 콘솔과 요금 화면에서 "이 연습이 만든 것"을 골라 볼 수 있다.
  default_tags {
    tags = {
      Project     = var.project
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}
