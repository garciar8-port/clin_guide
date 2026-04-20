# --- ECS Cluster ---
resource "aws_ecs_cluster" "main" {
  name = "${var.project_name}-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# --- CloudWatch Log Group ---
resource "aws_cloudwatch_log_group" "ecs" {
  name              = "/ecs/${var.project_name}-${var.environment}"
  retention_in_days = 30
}

# --- Cloud Map (Service Discovery) ---
resource "aws_service_discovery_private_dns_namespace" "main" {
  name = "${var.project_name}-${var.environment}.internal"
  vpc  = aws_vpc.main.id
}

resource "aws_service_discovery_service" "api" {
  name = "api"

  dns_config {
    namespace_id = aws_service_discovery_private_dns_namespace.main.id
    dns_records {
      type = "A"
      ttl  = 10
    }
  }

  health_check_custom_config {
    failure_threshold = 1
  }
}

# --- API Task Definition ---
resource "aws_ecs_task_definition" "api" {
  family                   = "${var.project_name}-${var.environment}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.main.repository_url}:${var.image_tag}"
      essential = true

      portMappings = [
        { containerPort = 8000, protocol = "tcp" }
      ]

      command = [
        "uvicorn", "clinguide.api.app:app",
        "--host", "0.0.0.0", "--port", "8000"
      ]

      secrets = [
        {
          name      = "CLINGUIDE_ANTHROPIC_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CLINGUIDE_ANTHROPIC_API_KEY::"
        },
        {
          name      = "CLINGUIDE_OPENAI_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CLINGUIDE_OPENAI_API_KEY::"
        },
        {
          name      = "CLINGUIDE_COHERE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CLINGUIDE_COHERE_API_KEY::"
        },
        {
          name      = "CLINGUIDE_PINECONE_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:CLINGUIDE_PINECONE_API_KEY::"
        },
      ]

      environment = [
        { name = "CLINGUIDE_HOST", value = "0.0.0.0" },
        { name = "CLINGUIDE_PORT", value = "8000" },
        { name = "CLINGUIDE_DEBUG", value = "false" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

# --- UI Task Definition ---
resource "aws_ecs_task_definition" "ui" {
  family                   = "${var.project_name}-${var.environment}-ui"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.ui_cpu
  memory                   = var.ui_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([
    {
      name      = "ui"
      image     = "${aws_ecr_repository.main.repository_url}:${var.image_tag}"
      essential = true

      portMappings = [
        { containerPort = 8501, protocol = "tcp" }
      ]

      command = [
        "streamlit", "run", "ui/app.py",
        "--server.port", "8501", "--server.address", "0.0.0.0"
      ]

      environment = [
        {
          name  = "CLINGUIDE_API_URL"
          value = "http://api.${var.project_name}-${var.environment}.internal:8000"
        },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs.name
          "awslogs-region"        = data.aws_region.current.name
          "awslogs-stream-prefix" = "ui"
        }
      }
    }
  ])
}

# --- API ECS Service ---
resource "aws_ecs_service" "api" {
  name            = "${var.project_name}-${var.environment}-api"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  service_registries {
    registry_arn = aws_service_discovery_service.api.arn
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener_rule.api]
}

# --- UI ECS Service ---
resource "aws_ecs_service" "ui" {
  name            = "${var.project_name}-${var.environment}-ui"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.ui.arn
  desired_count   = var.ui_desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_groups  = [aws_security_group.ecs.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ui.arn
    container_name   = "ui"
    container_port   = 8501
  }

  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.http]
}
