# AWS Serverless Image Optimizer (Terraform + Lambda@Edge)

Este proyecto despliega una infraestructura de optimización de imágenes en AWS. Intercepta peticiones en CloudFront y usa Lambda@Edge (Python) para convertir imágenes a **WebP** automáticamente si el cliente lo soporta.

## 📋 Prerrequisitos

* **Docker Desktop** (Debe estar corriendo para compilar las librerías de Python).
* **Terraform** (v1.0+).
* **AWS CLI** configurado con tus credenciales (`aws configure`).
* **Git**.

---

## 🚀 Despliegue Inicial (Paso a Paso)

### 1. Clonar el repositorio
```bash
git clone https://github.com/AlejandroCarbajalHernandez/aws-image-optimizer.git
cd webpConversion
code . 

# Limpia builds anteriores
rm -rf build/lambda_function.zip
mkdir -p build

# Compila usando arquitectura Linux x86_64
docker run --rm --platform linux/amd64 \
  -v "$(pwd)/lambda_src":/var/task \
  -v "$(pwd)/build":/build \
  public.ecr.aws/sam/build-python3.11:latest \
  /bin/sh -c "pip install --upgrade --force-reinstall -r requirements.txt -t . && zip -r /build/lambda_function.zip ."
  
terraform init 
terraform plan 
terraform apply --auto-approve

