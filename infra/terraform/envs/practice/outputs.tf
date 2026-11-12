# apply 가 끝나면 찍히는 값들. `terraform output` 으로 다시 볼 수 있다. 비밀 값은 없다(비밀은 위치만 낸다).

output "uploads_bucket_name" {
  description = "업로드 버킷의 이름"
  value       = module.storage.uploads_bucket_name
}

output "server_repository_url" {
  description = "server 이미지를 올릴 주소"
  value       = module.registry.server_repository_url
}

output "parser_repository_url" {
  description = "parser 이미지를 올릴 주소"
  value       = module.registry.parser_repository_url
}

output "nat_gateway_count" {
  description = "NAT 게이트웨이의 수"
  value       = module.network.nat_gateway_count
}

output "task_subnet_ids" {
  description = "태스크가 뜨는 서브넷. migrate 태스크를 손으로 돌릴 때 쓴다."
  value       = module.network.task_subnet_ids
}

output "worker_security_group_id" {
  description = "worker 의 보안 그룹. migrate 태스크를 손으로 돌릴 때 쓴다."
  value       = module.network.worker_security_group_id
}

output "redis_url" {
  description = "REDIS_URL 이 되는 값. 끄면 null."
  value       = var.enable_queue_redis ? module.queue_redis[0].redis_url : null
}

output "database_endpoint" {
  description = "Aurora 의 접속 주소. 끄면 null."
  value       = var.enable_database ? module.database[0].cluster_endpoint : null
}

output "database_cluster_arn" {
  description = "Aurora 클러스터의 ARN(Data API 용). 끄면 null."
  value       = var.enable_database ? module.database[0].cluster_arn : null
}

output "database_master_user_secret_arn" {
  description = "AWS 가 만든 주 사용자 비밀의 위치. 끄면 null."
  value       = var.enable_database ? module.database[0].master_user_secret_arn : null
}

output "database_url_secret_arn" {
  description = "DATABASE_URL 비밀 그릇의 위치. 값은 손으로 넣는다. 끄면 null."
  value       = var.enable_database ? module.database[0].database_url_secret_arn : null
}

output "migrate_database_url_secret_arn" {
  description = "MIGRATE_DATABASE_URL 비밀 그릇의 위치. 값은 손으로 넣는다. 끄면 null."
  value       = var.enable_database ? module.database[0].migrate_database_url_secret_arn : null
}

output "ecs_cluster_name" {
  description = "ECS 클러스터의 이름. 끄면 null."
  value       = var.enable_compute ? module.compute[0].cluster_name : null
}

output "alb_dns_name" {
  description = "api 의 바깥 주소. 끄면 null."
  value       = var.enable_compute ? module.compute[0].alb_dns_name : null
}

output "migrate_task_definition_arn" {
  description = "migrate 태스크 정의. 끄면 null."
  value       = var.enable_compute ? module.compute[0].migrate_task_definition_arn : null
}
