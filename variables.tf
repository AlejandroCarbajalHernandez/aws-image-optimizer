# variables.tf

variable "main_region" {
  description = "La región donde vive tu bucket (ej. Oregon o N. Virginia)"
  type        = string
  default     = "us-east-1"
}

variable "bucket_name" {
  description = "El nombre único para tu nuevo bucket S3"
  type        = string
  default     = "mi-nuevo-bucket-imagenes-ahcloud-v1" # Cambia esto por el nombre que quieras
}