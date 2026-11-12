output "uploads_bucket_name" {
  description = "업로드 버킷의 이름. 컨테이너의 S3_BUCKET 이 된다."
  value       = aws_s3_bucket.uploads.id
}

output "uploads_bucket_arn" {
  description = "업로드 버킷의 ARN(AWS 자원의 전체 이름). IAM 정책이 이 버킷만 가리키는 데 쓴다."
  value       = aws_s3_bucket.uploads.arn
}

output "frontend_bucket_name" {
  description = "프론트 버킷의 이름. 끄면 null."
  value       = var.enable_frontend_bucket ? aws_s3_bucket.frontend[0].id : null
}
