output "execution_role_arn" {
  description = "실행 역할의 ARN. 세 태스크 정의(api, worker, migrate)가 같이 쓴다."
  value       = aws_iam_role.execution.arn
}

output "api_task_role_arn" {
  description = "api 컨테이너 안의 코드가 쓰는 역할"
  value       = aws_iam_role.api_task.arn
}

output "worker_task_role_arn" {
  description = "worker 와 파서 컨테이너 안의 코드가 쓰는 역할"
  value       = aws_iam_role.worker_task.arn
}
