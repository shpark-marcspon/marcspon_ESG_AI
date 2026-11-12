output "primary_endpoint_address" {
  description = "주 노드의 주소(쓰기와 읽기). VPC 안에서만 풀린다."
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "redis_url" {
  description = "컨테이너의 REDIS_URL 이 되는 값. rediss:// 의 s 는 TLS 다. 비밀번호가 없으므로 비밀이 아니다(들어올 수 있는 곳을 보안 그룹이 막는다)."
  value       = "rediss://${aws_elasticache_replication_group.main.primary_endpoint_address}:6379"
}
