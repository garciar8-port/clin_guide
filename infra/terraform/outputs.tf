output "alb_dns_name" {
  description = "ALB DNS name — access the app at http://<this-value>"
  value       = aws_lb.main.dns_name
}

output "ecr_repository_url" {
  description = "ECR repository URL for docker push"
  value       = aws_ecr_repository.main.repository_url
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "s3_bucket_name" {
  description = "S3 bucket for SPL data"
  value       = aws_s3_bucket.spl_data.id
}

output "secret_arn" {
  description = "Secrets Manager ARN (populate via AWS console)"
  value       = aws_secretsmanager_secret.api_keys.arn
}
