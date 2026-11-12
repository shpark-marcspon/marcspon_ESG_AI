# 도구와 공급자의 버전을 여기서 고정한다. 공급자의 정확한 버전과 내려받은 파일의 지문은 .terraform.lock.hcl 에 적히고,
# 그 파일을 커밋한다 → 누가 언제 init 해도 같은 공급자를 받는다.
terraform {
  # ~> 1.16.5 : 1.16.5 이상, 1.17 미만. (bin/tf 가 쓰는 이미지는 정확히 1.16.5 다.)
  required_version = "~> 1.16.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "6.67.0"
    }
  }

  # 상태 파일(만든 자원의 기록)을 두는 곳. 지금은 적지 않았으므로 이 폴더의 terraform.tfstate(로컬 백엔드)가 된다.
  # 로컬 상태는 혼자 연습할 때만 쓴다. 그 파일을 잃으면 Terraform 은 자기가 만든 자원을 잊는다.
  # 둘 이상이 같이 쓰거나 오래 둘 환경이면 S3 에 둔다. 그때의 꼴(버킷은 이 코드 밖에서 먼저 만들어 둔다):
  #
  # backend "s3" {
  #   bucket       = "<상태 파일용 버킷 이름>"
  #   key          = "esg-app/practice/terraform.tfstate"
  #   region       = "ap-northeast-2"
  #   encrypt      = true
  #   use_lockfile = true   # 두 사람이 동시에 apply 하지 못하게 잠근다
  # }
}
