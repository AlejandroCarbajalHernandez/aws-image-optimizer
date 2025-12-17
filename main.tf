# main.tf

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# 1. Proveedores
# Este usará la región que definiste en variables.tf (us-east-1 por defecto)
provider "aws" {
  region = var.main_region
}

# Proveedor ESPECÍFICO para Lambda@Edge (SIEMPRE debe ser us-east-1)
provider "aws" {
  alias  = "useast1"
  region = "us-east-1"
}

# 2. Creación del Bucket S3 y Seguridad
resource "aws_s3_bucket" "new_bucket" {
  bucket        = var.bucket_name
  force_destroy = true 
}

resource "aws_s3_bucket_public_access_block" "block_public_access" {
  bucket = aws_s3_bucket.new_bucket.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_cloudfront_origin_access_control" "oac" {
  name                              = "oac-${var.bucket_name}"
  description                       = "OAC para restringir acceso solo a CloudFront"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# 3. Construcción del Paquete Lambda
resource "null_resource" "build_lambda_package" {
  triggers = {
    code_diff = filesha256("${path.module}/lambda_src/lambda_function.py")
    req_diff  = filesha256("${path.module}/lambda_src/requirements.txt")
  }

  provisioner "local-exec" {
    command = <<EOT
      docker run --rm -v ${path.module}/lambda_src:/var/task \
      -v ${path.module}/build:/build \
      public.ecr.aws/sam/build-python3.11:latest \
      /bin/sh -c "pip install -r requirements.txt -t . && zip -r /build/lambda_function.zip ."
    EOT
  }
}

data "local_file" "lambda_zip" {
  filename   = "${path.module}/build/lambda_function.zip"
  depends_on = [null_resource.build_lambda_package]
}

# 4. IAM y Roles
resource "aws_iam_role" "lambda_edge_role" {
  name = "image_optimizer_edge_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = ["lambda.amazonaws.com", "edgelambda.amazonaws.com"]
      }
    }]
  })
}

resource "aws_iam_policy" "lambda_logging_s3" {
  name        = "lambda_edge_logging_s3"
  description = "IAM policy for logging and s3 read"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"]
        Effect   = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action   = ["s3:GetObject"]
        Effect   = "Allow"
        Resource = "${aws_s3_bucket.new_bucket.arn}/*"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_logs" {
  role       = aws_iam_role.lambda_edge_role.name
  policy_arn = aws_iam_policy.lambda_logging_s3.arn
}

# 5. Función Lambda (En us-east-1)
resource "aws_lambda_function" "image_optimizer" {
  provider         = aws.useast1
  filename         = data.local_file.lambda_zip.filename
  function_name    = "image-optimizer-edge"
  role             = aws_iam_role.lambda_edge_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.11"
  source_code_hash = filebase64sha256(data.local_file.lambda_zip.filename)
  timeout          = 10
  memory_size      = 1024
  publish          = true
}

# 6. CloudFront
resource "aws_cloudfront_distribution" "s3_distribution" {
  origin {
    domain_name              = aws_s3_bucket.new_bucket.bucket_regional_domain_name
    origin_id                = "S3Origin"
    origin_access_control_id = aws_cloudfront_origin_access_control.oac.id
  }

  enabled         = true
  is_ipv6_enabled = true
  comment         = "Optimización de Imágenes - ${var.bucket_name}"

  default_cache_behavior {
    allowed_methods  = ["GET", "HEAD", "OPTIONS"]
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3Origin"

    forwarded_values {
      query_string = false
      headers      = ["Accept"]
      cookies { forward = "none" }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 86400
    max_ttl                = 31536000

    lambda_function_association {
      event_type   = "origin-response"
      lambda_arn   = aws_lambda_function.image_optimizer.qualified_arn
      include_body = false
    }
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate { cloudfront_default_certificate = true }
}

# 7. Política de Bucket (Permiso final para CloudFront)
resource "aws_s3_bucket_policy" "allow_cloudfront_oac" {
  bucket = aws_s3_bucket.new_bucket.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "AllowCloudFrontServicePrincipal"
        Effect    = "Allow"
        Principal = { Service = "cloudfront.amazonaws.com" }
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.new_bucket.arn}/*"
        Condition = {
          StringEquals = {
            "AWS:SourceArn" = aws_cloudfront_distribution.s3_distribution.arn
          }
        }
      }
    ]
  })
}

# Outputs
output "cloudfront_url" {
  value = "https://${aws_cloudfront_distribution.s3_distribution.domain_name}"
}