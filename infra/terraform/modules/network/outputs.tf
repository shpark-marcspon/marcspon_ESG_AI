output "vpc_id" {
  description = "VPC 의 id"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "공개 서브넷 둘. ALB 가 여기에 선다."
  value       = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

output "private_subnet_ids" {
  description = "사설 서브넷 둘. Aurora 와 Redis 가 여기에 선다."
  value       = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

# ★ 두 구성의 갈림이 이 두 출력에 모여 있다. compute 모듈은 이 둘만 받아 쓴다.
output "task_subnet_ids" {
  description = "ECS 태스크를 띄울 서브넷. NAT 를 켜면 사설, 끄면 공개."
  value       = var.enable_nat_gateway ? [aws_subnet.private_a.id, aws_subnet.private_b.id] : [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

output "task_assign_public_ip" {
  description = "ECS 태스크에 공인 IP 를 붙이는가. NAT 가 없으면 붙여야 이미지를 받으러 바깥에 나갈 수 있다."
  value       = !var.enable_nat_gateway
}

output "alb_security_group_id" {
  description = "ALB 의 보안 그룹"
  value       = aws_security_group.alb.id
}

output "api_security_group_id" {
  description = "api 태스크의 보안 그룹"
  value       = aws_security_group.api.id
}

output "worker_security_group_id" {
  description = "worker 태스크의 보안 그룹"
  value       = aws_security_group.worker.id
}

output "database_security_group_id" {
  description = "Aurora 의 보안 그룹"
  value       = aws_security_group.database.id
}

output "redis_security_group_id" {
  description = "Redis 의 보안 그룹"
  value       = aws_security_group.redis.id
}

output "nat_gateway_count" {
  description = "NAT 게이트웨이의 수(0 또는 1). 돈이 드는 자원이라 눈에 보이게 낸다."
  value       = length(aws_nat_gateway.main)
}
