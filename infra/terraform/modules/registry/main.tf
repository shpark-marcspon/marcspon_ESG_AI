# ─────────────────────────────────────────────────────────────────────────────
# registry: 컨테이너 이미지를 올려 두는 곳(ECR). compose 의 `build:` 가 만든 이미지가 여기로 온다.
#
# 이미지는 둘이다: server(api·worker·migrate 가 같이 쓴다)와 parser.
# 이미지를 실제로 만들고 올리는 일(docker build, docker push)은 Terraform 이 하지 않는다. 사람이나 CI 가 한다.
# ─────────────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "server" {
  name = "${var.name}/server"

  # IMMUTABLE: 한 번 올린 태그를 덮어쓰지 못한다. "abc123 태그의 이미지"가 언제나 같은 내용임을 보장한다.
  # 그래서 태그는 latest 가 아니라 커밋마다 다른 값(예: git 커밋 해시)을 쓴다.
  image_tag_mutability = "IMMUTABLE"

  # 올릴 때 알려진 취약점을 훑는다(기본 검사는 요금이 없다).
  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = var.force_delete
}

resource "aws_ecr_repository" "parser" {
  name = "${var.name}/parser"

  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  force_delete = var.force_delete
}

# 정리 규칙. 이미지는 올릴 때마다 쌓이고 저장 요금이 든다. 규칙은 번호(rulePriority)가 작은 것부터 본다.
#   1. 태그가 없는 이미지(빌드 중간 산물, 밀려난 것)는 며칠 뒤에 지운다
#   2. 그 밖에는 최근 N 개만 남긴다
# 이 JSON 의 꼴은 ECR 이 정한 것이다(Terraform 의 문법이 아니다). 두 저장소가 같은 규칙을 쓴다.
locals {
  lifecycle_policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_expire_days
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the most recent images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.keep_image_count
        }
        action = { type = "expire" }
      },
    ]
  })
}

resource "aws_ecr_lifecycle_policy" "server" {
  repository = aws_ecr_repository.server.name
  policy     = local.lifecycle_policy
}

resource "aws_ecr_lifecycle_policy" "parser" {
  repository = aws_ecr_repository.parser.name
  policy     = local.lifecycle_policy
}
