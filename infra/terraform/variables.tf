variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "prod"], var.environment)
    error_message = "Environment must be dev or prod."
  }
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "clinguide"
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "api_cpu" {
  description = "API task CPU units (1 vCPU = 1024)"
  type        = number
  default     = 512
}

variable "api_memory" {
  description = "API task memory in MiB"
  type        = number
  default     = 1024
}

variable "ui_cpu" {
  description = "UI task CPU units"
  type        = number
  default     = 256
}

variable "ui_memory" {
  description = "UI task memory in MiB"
  type        = number
  default     = 512
}

variable "api_desired_count" {
  description = "Number of API task instances"
  type        = number
  default     = 1
}

variable "ui_desired_count" {
  description = "Number of UI task instances"
  type        = number
  default     = 1
}
