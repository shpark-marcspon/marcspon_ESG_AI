output "cluster_endpoint" {
  description = "쓰기용 접속 주소. 접속 주소 비밀의 값을 만들 때 호스트 자리에 넣는다."
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_port" {
  description = "접속 포트(5432)"
  value       = aws_rds_cluster.main.port
}

output "cluster_arn" {
  description = "클러스터의 ARN. Data API 로 SQL 을 보낼 때 쓴다."
  value       = aws_rds_cluster.main.arn
}

output "database_name" {
  description = "데이터베이스 이름"
  value       = aws_rds_cluster.main.database_name
}

output "master_user_secret_arn" {
  description = "AWS 가 만든 주 사용자 비밀(사용자 이름과 비밀번호)의 ARN. 값이 아니라 위치다."
  value       = aws_rds_cluster.main.master_user_secret[0].secret_arn
}

output "database_url_secret_arn" {
  description = "DATABASE_URL 비밀 그릇의 ARN"
  value       = aws_secretsmanager_secret.database_url.arn
}

output "migrate_database_url_secret_arn" {
  description = "MIGRATE_DATABASE_URL 비밀 그릇의 ARN"
  value       = aws_secretsmanager_secret.migrate_database_url.arn
}
