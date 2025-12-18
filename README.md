# AWS Serverless Image Optimizer (Terraform + Lambda@Edge)

This project deploys an image optimization infrastructure on AWS. It intercepts requests in CloudFront and uses Lambda@Edge (Python) to automatically convert images to **WebP** .

## 📋 Prerequisites

* **Docker Desktop** (Must be running to compile Python libraries).
* **Terraform** (v1.0+).
* **AWS CLI** configured with your credentials (`aws configure`).
* **Git**.

---

## 🚀 Initial Deployment (Step-by-Step)

### 1. Clone the repository
```bash
git clone [https://github.com/AlejandroCarbajalHernandez/aws-image-optimizer.git](https://github.com/AlejandroCarbajalHernandez/aws-image-optimizer.git)
cd webpConversion
code .

# Remember to change the name of the s3 bucket to one you like in variables.tf
# Clean previous builds
rm -rf build/lambda_function.zip
mkdir -p build

# Compile using Linux x86_64 architecture (required for AWS Lambda)
docker run --rm --platform linux/amd64 \
  -v "$(pwd)/lambda_src":/var/task \
  -v "$(pwd)/build":/build \
  public.ecr.aws/sam/build-python3.11:latest \
  /bin/sh -c "pip install --upgrade --force-reinstall -r requirements.txt -t . && zip -r /build/lambda_function.zip ."
  
# Initialize Terraform
terraform init 

# Verify the execution plan
terraform plan 

# Apply changes to deploy infrastructure
terraform apply --auto-approve