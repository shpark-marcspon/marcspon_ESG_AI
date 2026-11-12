output "api_log_group_name" {
  description = "api 의 로그 그룹 이름"
  value       = aws_cloudwatch_log_group.api.name
}

output "worker_log_group_name" {
  description = "worker 의 로그 그룹 이름"
  value       = aws_cloudwatch_log_group.worker.name
}

output "parser_log_group_name" {
  description = "파서의 로그 그룹 이름"
  value       = aws_cloudwatch_log_group.parser.name
}

output "migrate_log_group_name" {
  description = "migrate 의 로그 그룹 이름"
  value       = aws_cloudwatch_log_group.migrate.name
}

output "log_group_arns" {
  description = "네 로그 그룹의 ARN. 실행 역할이 이 그룹들에만 쓰게 하는 데 쓴다."
  value = [
    aws_cloudwatch_log_group.api.arn,
    aws_cloudwatch_log_group.worker.arn,
    aws_cloudwatch_log_group.parser.arn,
    aws_cloudwatch_log_group.migrate.arn,
  ]
}
