output "cluster_name" {
  description = "ECS 클러스터의 이름"
  value       = aws_ecs_cluster.main.name
}

output "alb_dns_name" {
  description = "ALB 의 주소. https://<이 값>/healthz 로 api 에 닿는다(80 은 443 으로 돌려보낸다). 인증서의 도메인이 이 주소를 가리켜야 인증서 확인이 통과한다."
  value       = aws_lb.api.dns_name
}

output "api_service_name" {
  description = "api 서비스의 이름"
  value       = aws_ecs_service.api.name
}

output "worker_service_name" {
  description = "worker 서비스의 이름"
  value       = aws_ecs_service.worker.name
}

output "migrate_task_definition_arn" {
  description = "migrate 태스크 정의의 ARN. run-task 에 넘긴다."
  value       = aws_ecs_task_definition.migrate.arn
}
