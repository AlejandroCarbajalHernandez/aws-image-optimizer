import json
import base64
from io import BytesIO
from PIL import Image
import boto3  # Librería oficial de AWS (viene incluida)

# Inicializamos el cliente S3 fuera del handler para reusar conexiones
s3_client = boto3.client('s3')

def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    response = event['Records'][0]['cf']['response']
    headers = request['headers']

    # Si la respuesta original de S3 no es 200, devolverla tal cual (ej. 404 not found)
    if int(response['status']) >= 400:
        return response

    # 1. DETECTAR EL BUCKET DINÁMICAMENTE
    # CloudFront nos dice de dónde viene la imagen en el evento
    try:
        s3_domain = request['origin']['s3']['domainName']
        # El dominio suele ser "nombre-bucket.s3.region.amazonaws.com"
        # Extraemos solo el nombre del bucket:
        bucket_name = s3_domain.split('.')[0]
    except KeyError:
        # Fallback de seguridad por si algo raro pasa con el origen
        print("No se pudo detectar el origen S3, devolviendo original")
        return response

    # 2. VERIFICAR SI EL CLIENTE SOPORTA WEBP
    accept_webp = False
    if 'accept' in headers:
        for header in headers['accept']:
            if 'image/webp' in header['value']:
                accept_webp = True
                break
    
    # Si no soporta WebP, no gastamos memoria procesando, devolvemos la original
    if not accept_webp:
        return response

    try:
        # 3. OBTENER LA IMAGEN DE FORMA SEGURA (BOTO3)
        # request['uri'] viene como "/imagen.jpg", quitamos la barra inicial
        key = request['uri'].lstrip('/')
        
        # Usamos boto3 para leer el bucket privado usando el Rol de IAM de la Lambda
        s3_response = s3_client.get_object(Bucket=bucket_name, Key=key)
        image_data = s3_response['Body'].read()

        # 4. PROCESAR CON PILLOW
        img = Image.open(BytesIO(image_data))
        buffer = BytesIO()
        
        # Convertir a WebP
        img.save(buffer, format="WEBP", quality=80)
        
        # 5. PREPARAR RESPUESTA
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # Limite de Lambda@Edge para el body generado es 1.3 MB
        if len(img_str) > 1300000:
            print("Imagen convertida muy grande, devolviendo original")
            return response

        # Modificar la respuesta para devolver la nueva imagen
        response['status'] = '200'
        response['statusDescription'] = 'OK'
        response['body'] = img_str
        response['bodyEncoding'] = 'base64'
        response['headers']['content-type'] = [{'key': 'Content-Type', 'value': 'image/webp'}]
        # Importante: Variar cache por Accept header para no servir WebP a quien no lo soporta
        response['headers']['vary'] = [{'key': 'Vary', 'value': 'Accept'}]
        
        return response

    except Exception as e:
        print(f"Error procesando imagen: {str(e)}")
        # Fail Open: Si algo falla, el usuario ve la imagen original (png/jpg)
        return response