# ─────────────────────────────────────────────────────────────────────────────
# storage: 원본 파일을 두는 S3 버킷. compose 의 storage(S3 호환 저장소)에 대응한다.
#
# 올리는 흐름(지금 앱의 꼴): api 가 "서명된 주소"를 만들어 주면, 클라이언트가 그 주소로 버킷에 직접 PUT 한다.
# 파일이 api 를 지나가지 않는다. 그래서 버킷은 ① 바깥에 공개되지 않으면서 ② 서명된 요청은 받아야 한다.
#
# S3 는 버킷 하나의 설정이 여러 자원으로 나뉘어 있다(공개 차단, 암호화, CORS, 수명 주기 …). 하나씩 적는다.
# ─────────────────────────────────────────────────────────────────────────────

# 버킷. 이름은 전 세계에서 하나뿐이어야 해서, 앞머리만 정하고 뒤는 AWS 가 무작위로 붙이게 한다.
resource "aws_s3_bucket" "uploads" {
  bucket_prefix = "${var.name}-uploads-"
  force_destroy = var.force_destroy
}

# 공개 차단 넷. 넷 다 켜 두면, 나중에 누가 공개 ACL 이나 공개 정책을 달려고 해도 S3 가 거절하거나 무시한다.
#   block_public_acls       공개 ACL 을 새로 다는 요청을 거절한다
#   ignore_public_acls      이미 달린 공개 ACL 이 있어도 없는 셈 친다
#   block_public_policy     공개를 허용하는 버킷 정책을 다는 요청을 거절한다
#   restrict_public_buckets 공개 정책이 있어도 바깥 계정과 익명의 접근을 막는다
# 서명된 주소는 "공개"가 아니다(서명한 역할의 권한으로 들어온다). 그래서 넷을 다 켜도 업로드는 된다.
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

# 소유권: ACL(파일마다 붙이던 옛 권한 방식)을 아예 끈다. 권한은 IAM 정책과 버킷 정책으로만 정한다.
resource "aws_s3_bucket_ownership_controls" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

# 저장할 때의 암호화. AES256 = S3 가 관리하는 키(SSE-S3)로, 추가 요금과 설정이 없다.
# 새 버킷은 적지 않아도 이렇게 되지만, "암호화가 있다"를 코드와 테스트에서 볼 수 있게 적는다.
# 키를 직접 통제해야 하면(감사 기록, 키 폐기) sse_algorithm 을 "aws:kms" 로 바꾸고 KMS 키를 만든다.
resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# 버킷 정책: 암호화되지 않은 연결(http)로 온 요청은 누구의 것이든 거절한다.
# IAM 에서 Deny 는 Allow 를 이긴다. 그래서 "어떤 경우에도 안 된다"는 규칙은 Deny 로 적는다.
resource "aws_s3_bucket_policy" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyInsecureTransport"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          aws_s3_bucket.uploads.arn,
          "${aws_s3_bucket.uploads.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
    ]
  })

  # 공개 차단이 먼저 걸린 뒤에 정책을 단다(둘을 동시에 바꾸면 S3 가 충돌 오류를 내는 일이 있다).
  depends_on = [aws_s3_bucket_public_access_block.uploads]
}

# CORS: 브라우저는 다른 주소(우리 화면 → S3)로 보내는 요청을 기본으로 막는다.
# 버킷이 "이 주소의 화면에서 온 PUT 은 받는다"고 말해 줘야 브라우저가 보낸다. curl 과 서버끼리는 CORS 와 무관하다.
resource "aws_s3_bucket_cors_configuration" "uploads" {
  count = length(var.cors_allowed_origins) > 0 ? 1 : 0

  bucket = aws_s3_bucket.uploads.id

  cors_rule {
    allowed_origins = var.cors_allowed_origins
    allowed_methods = ["PUT", "GET", "HEAD"]
    # 브라우저가 붙여 보내는 헤더(Content-Type 등)를 가리지 않고 받는다.
    allowed_headers = ["*"]
    # 브라우저의 코드가 응답에서 읽을 수 있는 헤더. ETag 는 올라간 파일의 지문이다.
    expose_headers = ["ETag"]
    # 브라우저가 이 허락을 기억해 두는 시간(초)
    max_age_seconds = 3000
  }
}

# 수명 주기: 큰 파일을 조각으로 올리다 만 것(멀티파트 업로드)은 목록에 안 보이면서 요금이 나간다. 며칠 뒤에 지운다.
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "abort-incomplete-multipart-uploads"
    status = "Enabled"

    # 빈 filter = 버킷의 모든 파일에 적용
    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = var.abort_incomplete_upload_days
    }
  }
}

# ── 정적 프론트용 버킷 (자리만. 기본은 끔) ───────────────────────────────────
# React 빌드 결과를 두는 곳. 이 버킷도 공개하지 않는다. 바깥에는 CloudFront(CDN)가 서고,
# CloudFront 만 이 버킷을 읽게 한다(OAC). CloudFront 와 그 버킷 정책은 아직 적지 않았다.

resource "aws_s3_bucket" "frontend" {
  count = var.enable_frontend_bucket ? 1 : 0

  bucket_prefix = "${var.name}-frontend-"
  force_destroy = var.force_destroy
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  count = var.enable_frontend_bucket ? 1 : 0

  bucket = aws_s3_bucket.frontend[0].id

  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  count = var.enable_frontend_bucket ? 1 : 0

  bucket = aws_s3_bucket.frontend[0].id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}
