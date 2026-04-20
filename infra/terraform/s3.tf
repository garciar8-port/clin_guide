resource "aws_s3_bucket" "spl_data" {
  bucket = "${var.project_name}-spl-data-${data.aws_caller_identity.current.account_id}-${var.environment}"
}

resource "aws_s3_bucket_versioning" "spl_data" {
  bucket = aws_s3_bucket.spl_data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "spl_data" {
  bucket = aws_s3_bucket.spl_data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "spl_data" {
  bucket                  = aws_s3_bucket.spl_data.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_lifecycle_configuration" "spl_data" {
  bucket = aws_s3_bucket.spl_data.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"
    transition {
      days          = 90
      storage_class = "STANDARD_IA"
    }
  }
}
