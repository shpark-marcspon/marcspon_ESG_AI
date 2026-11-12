# (가) 업로드 버킷: 공개 차단 넷이 모두 켜져 있고, 암호화가 있다.
#
# 이 폴더의 테스트는 전부 "모의 공급자" 위에서 돈다. mock_provider 는 AWS 에 묻지 않고 가짜 값을 지어내는 공급자다.
# 계정도 자격 증명도 네트워크도 필요 없다. 대신 확인하는 것은 "Terraform 이 AWS 에 무엇을 보내려 하는가(계획)"까지다.
# AWS 가 그것을 받아 주는지는 여기서 알 수 없다(infra/README.md 의 「계정 없이 확인한 것과 못 한 것」).

mock_provider "aws" {
  # AWS 가 정해 주는 값(id, arn)은 계획 단계에서 "아직 모름"이다. 모의 공급자가 계획 단계에서도 가짜 값을 주게 한다.
  override_during = plan

  mock_resource "aws_s3_bucket" {
    defaults = {
      id  = "test-uploads-bucket"
      arn = "arn:aws:s3:::test-uploads-bucket"
    }
  }
}

run "uploads_bucket_blocks_public_access_and_is_encrypted" {
  command = plan

  # 환경 전체가 아니라 storage 모듈 하나만 불러 본다. 그래야 모듈 안의 자원을 직접 가리킬 수 있다.
  module {
    source = "../../modules/storage"
  }

  variables {
    name = "test"
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.uploads.block_public_acls == true
    error_message = "업로드 버킷의 공개 차단 block_public_acls 가 꺼져 있다."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.uploads.ignore_public_acls == true
    error_message = "업로드 버킷의 공개 차단 ignore_public_acls 가 꺼져 있다."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.uploads.block_public_policy == true
    error_message = "업로드 버킷의 공개 차단 block_public_policy 가 꺼져 있다."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.uploads.restrict_public_buckets == true
    error_message = "업로드 버킷의 공개 차단 restrict_public_buckets 가 꺼져 있다."
  }

  assert {
    condition     = aws_s3_bucket_public_access_block.uploads.bucket == aws_s3_bucket.uploads.id
    error_message = "공개 차단이 업로드 버킷이 아닌 다른 버킷에 걸려 있다."
  }

  # 암호화 설정 자원이 업로드 버킷에 걸려 있고, 방식이 SSE-S3(AES256) 또는 KMS 다.
  assert {
    condition     = aws_s3_bucket_server_side_encryption_configuration.uploads.bucket == aws_s3_bucket.uploads.id
    error_message = "암호화 설정이 업로드 버킷에 걸려 있지 않다."
  }

  assert {
    condition = alltrue([
      for r in aws_s3_bucket_server_side_encryption_configuration.uploads.rule :
      contains(["AES256", "aws:kms", "aws:kms:dsse"], r.apply_server_side_encryption_by_default[0].sse_algorithm)
    ]) && length(aws_s3_bucket_server_side_encryption_configuration.uploads.rule) == 1
    error_message = "업로드 버킷의 기본 암호화 규칙이 없거나 알 수 없는 방식이다."
  }

  # ACL 을 끈 상태(권한은 정책으로만)
  assert {
    condition     = aws_s3_bucket_ownership_controls.uploads.rule[0].object_ownership == "BucketOwnerEnforced"
    error_message = "업로드 버킷에서 ACL 이 꺼져 있지 않다(BucketOwnerEnforced 가 아니다)."
  }

  # 버킷 정책: 암호화되지 않은 연결을 거절하는 Deny 문장만 있다(Allow 로 여는 문장이 없다).
  assert {
    condition = alltrue([
      for s in jsondecode(aws_s3_bucket_policy.uploads.policy).Statement : s.Effect == "Deny"
    ])
    error_message = "업로드 버킷의 정책에 Allow 문장이 있다. 버킷 정책으로는 열지 않는다(권한은 역할의 정책으로 준다)."
  }

  # 올리다 만 조각을 지우는 규칙이 켜져 있다.
  assert {
    condition     = aws_s3_bucket_lifecycle_configuration.uploads.rule[0].status == "Enabled" && aws_s3_bucket_lifecycle_configuration.uploads.rule[0].abort_incomplete_multipart_upload[0].days_after_initiation == 7
    error_message = "미완료 업로드 정리 규칙이 꺼져 있거나 기간이 기본값(7일)이 아니다."
  }

  # 기본값에서는 CORS 규칙도 프론트 버킷도 없다.
  assert {
    condition     = length(aws_s3_bucket_cors_configuration.uploads) == 0 && length(aws_s3_bucket.frontend) == 0
    error_message = "기본값인데 CORS 규칙이나 프론트 버킷이 만들어진다."
  }
}

run "cors_rule_appears_only_when_origins_are_given" {
  command = plan

  module {
    source = "../../modules/storage"
  }

  variables {
    name                 = "test"
    cors_allowed_origins = ["https://app.example.com"]
  }

  assert {
    condition     = length(aws_s3_bucket_cors_configuration.uploads) == 1
    error_message = "화면 주소를 줬는데 CORS 규칙이 만들어지지 않는다."
  }

  assert {
    condition = alltrue([
      for r in aws_s3_bucket_cors_configuration.uploads[0].cors_rule :
      r.allowed_origins == toset(["https://app.example.com"]) && contains(r.allowed_methods, "PUT") && !contains(r.allowed_origins, "*")
    ])
    error_message = "CORS 규칙이 준 주소만 허용하지 않거나 PUT 을 허용하지 않는다."
  }
}

run "frontend_bucket_is_private_when_enabled" {
  command = plan

  module {
    source = "../../modules/storage"
  }

  variables {
    name                   = "test"
    enable_frontend_bucket = true
  }

  assert {
    condition     = length(aws_s3_bucket.frontend) == 1 && length(aws_s3_bucket_public_access_block.frontend) == 1
    error_message = "프론트 버킷을 켰는데 버킷이나 공개 차단이 만들어지지 않는다."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.frontend[0].block_public_acls,
      aws_s3_bucket_public_access_block.frontend[0].ignore_public_acls,
      aws_s3_bucket_public_access_block.frontend[0].block_public_policy,
      aws_s3_bucket_public_access_block.frontend[0].restrict_public_buckets,
    ])
    error_message = "프론트 버킷의 공개 차단 넷 가운데 꺼진 것이 있다."
  }
}
