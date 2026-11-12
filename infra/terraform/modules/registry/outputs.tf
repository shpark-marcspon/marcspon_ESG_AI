output "server_repository_url" {
  description = "server 이미지를 올리고 받는 주소(<계정>.dkr.ecr.<리전>.amazonaws.com/<이름>). 뒤에 :태그 를 붙여 쓴다."
  value       = aws_ecr_repository.server.repository_url
}

output "parser_repository_url" {
  description = "parser 이미지를 올리고 받는 주소"
  value       = aws_ecr_repository.parser.repository_url
}

output "server_repository_arn" {
  description = "server 저장소의 ARN. 실행 역할이 이 저장소에서만 이미지를 받게 하는 데 쓴다."
  value       = aws_ecr_repository.server.arn
}

output "parser_repository_arn" {
  description = "parser 저장소의 ARN"
  value       = aws_ecr_repository.parser.arn
}
