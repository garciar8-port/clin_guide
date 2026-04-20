# ClinGuide — AWS Infrastructure

Two equivalent IaC implementations (CloudFormation and Terraform) for deploying ClinGuide to AWS ECS Fargate. **Deploy with one, not both.**

## Architecture

```
Internet --> ALB (public subnets)
               |
               ├── /query, /health, /chunks/* --> API Service (Fargate, private subnet)
               └── /* (default)               --> UI Service  (Fargate, private subnet)
                                                     |
                                                     └── http://api.clinguide-dev.internal:8000
                                                          (Cloud Map service discovery)
```

**Resources created:** VPC (2 AZs), ALB, ECS Cluster, 2 Fargate services, ECR, S3, Secrets Manager, IAM roles, Cloud Map namespace.

## Prerequisites

- AWS CLI v2 configured (`aws configure`)
- Docker installed and running
- API keys ready: Anthropic, OpenAI, Cohere, Pinecone

## Option A: CloudFormation

Deploy stacks in order (each depends on exports from the previous):

```bash
cd infra/cloudformation

# 1. Network
aws cloudformation deploy --template-file network.yml \
  --stack-name clinguide-dev-network \
  --parameter-overrides Environment=dev

# 2. ECR
aws cloudformation deploy --template-file ecr.yml \
  --stack-name clinguide-dev-ecr \
  --parameter-overrides Environment=dev

# 3. Secrets (then populate via console or CLI)
aws cloudformation deploy --template-file secrets.yml \
  --stack-name clinguide-dev-secrets \
  --parameter-overrides Environment=dev

# Populate secrets:
aws secretsmanager put-secret-value \
  --secret-id clinguide/dev/api-keys \
  --secret-string '{"CLINGUIDE_ANTHROPIC_API_KEY":"sk-...","CLINGUIDE_OPENAI_API_KEY":"sk-...","CLINGUIDE_COHERE_API_KEY":"...","CLINGUIDE_PINECONE_API_KEY":"..."}'

# 4. S3
aws cloudformation deploy --template-file s3.yml \
  --stack-name clinguide-dev-s3 \
  --parameter-overrides Environment=dev

# 5. IAM (needs secret ARN and S3 bucket ARN from previous stacks)
SECRET_ARN=$(aws cloudformation describe-stacks --stack-name clinguide-dev-secrets \
  --query "Stacks[0].Outputs[?OutputKey=='SecretArn'].OutputValue" --output text)
BUCKET_ARN=$(aws cloudformation describe-stacks --stack-name clinguide-dev-s3 \
  --query "Stacks[0].Outputs[?OutputKey=='BucketArn'].OutputValue" --output text)

aws cloudformation deploy --template-file iam.yml \
  --stack-name clinguide-dev-iam \
  --parameter-overrides Environment=dev SecretArn=$SECRET_ARN S3BucketArn=$BUCKET_ARN \
  --capabilities CAPABILITY_NAMED_IAM

# 6. Push Docker image to ECR first
../scripts/deploy.sh latest dev   # or just the push steps

# 7. ECS (cluster, ALB, services)
aws cloudformation deploy --template-file ecs.yml \
  --stack-name clinguide-dev-ecs \
  --parameter-overrides Environment=dev ImageTag=latest
```

### Tear down (reverse order)

```bash
aws cloudformation delete-stack --stack-name clinguide-dev-ecs
aws cloudformation delete-stack --stack-name clinguide-dev-iam
aws cloudformation delete-stack --stack-name clinguide-dev-s3
aws cloudformation delete-stack --stack-name clinguide-dev-secrets
aws cloudformation delete-stack --stack-name clinguide-dev-ecr
aws cloudformation delete-stack --stack-name clinguide-dev-network
```

## Option B: Terraform

```bash
cd infra/terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars as needed

terraform init
terraform plan
terraform apply

# Populate secrets after apply:
aws secretsmanager put-secret-value \
  --secret-id clinguide/dev/api-keys \
  --secret-string '{"CLINGUIDE_ANTHROPIC_API_KEY":"sk-...","CLINGUIDE_OPENAI_API_KEY":"sk-...","CLINGUIDE_COHERE_API_KEY":"...","CLINGUIDE_PINECONE_API_KEY":"..."}'

# Push Docker image:
../scripts/deploy.sh latest dev
```

### Tear down

```bash
terraform destroy
```

## Deploy Script

After infrastructure is up, use the deploy script for subsequent deployments:

```bash
./infra/scripts/deploy.sh              # tags with git SHA, env=dev
./infra/scripts/deploy.sh v1.0.0       # custom tag
./infra/scripts/deploy.sh latest prod  # prod environment
```

## Cost Estimate (~$73/month)

| Resource | Monthly |
|----------|---------|
| NAT Gateway | ~$32 |
| ALB | ~$16 |
| Fargate API (512 CPU / 1 GB) | ~$15 |
| Fargate UI (256 CPU / 0.5 GB) | ~$8 |
| Secrets Manager | ~$0.40 |
| S3 + CloudWatch | < $2 |

Tear down when not in use to minimize costs.
