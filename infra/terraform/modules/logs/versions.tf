# 이 모듈이 요구하는 도구와 공급자. 정확한 버전은 모듈을 엮는 쪽(envs/practice/versions.tf)이 고정한다.
terraform {
  required_version = ">= 1.16.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 6.0"
    }
  }
}
