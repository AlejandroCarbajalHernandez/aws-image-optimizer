import json
import base64
import urllib.request
from io import BytesIO
from PIL import Image # Esta libreria la instalaremos en el paso 3

def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    response = event['Records'][0]['cf']['response']
    headers = request['headers']
    
    # URL de tu Bucket (Fijo para evitar bucle infinito con CloudFront)
    BUCKET_URL = "https://biblioteca-img-clientes.s3.us-west-2.amazonaws.com"
    
    # Si la respuesta original no es 200, devolverla tal cual
    if response['status'] != '200':
        return response

    # Verificar si el cliente soporta WebP
    accept_webp = False
    if 'accept' in headers:
        for header in headers['accept']:
            if 'image/webp' in header['value']:
                accept_webp = True
                break

    try:
        # 1. Obtener la imagen original directamente de S3
        image_url = BUCKET_URL + request['uri']
        
        # Usamos urllib estándar para no tener que instalar 'requests' y ahorrar espacio
        with urllib.request.urlopen(image_url) as url_response:
            image_data = url_response.read()

        # 2. Procesar imagen con Pillow
        img = Image.open(BytesIO(image_data))
        buffer = BytesIO()
        
        # Si soporta WebP, convertimos
        if accept_webp:
            img.save(buffer, format="WEBP", quality=80)
            content_type = 'image/webp'
        else:
            # Si no, devolvemos PNG/JPG original pero optimizado
            original_format = img.format if img.format else 'PNG'
            img.save(buffer, format=original_format, optimize=True)
            content_type = response['headers']['content-type'][0]['value']

        # 3. Preparar respuesta base64 para CloudFront
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # CloudFront tiene limite de 1MB para respuestas generadas (Lambda limits)
        if len(img_str) > 1300000: # Margen de seguridad (1.3MB en base64 es aprox 1MB binario)
            print("Imagen muy grande, devolviendo original")
            return response

        # Actualizar headers
        response['status'] = '200'
        response['statusDescription'] = 'OK'
        response['body'] = img_str
        response['bodyEncoding'] = 'base64'
        response['headers']['content-type'] = [{'key': 'Content-Type', 'value': content_type}]
        
        return response

    except Exception as e:
        print(f"Error procesando imagen: {str(e)}")
        # En caso de error, devolvemos la respuesta original de S3 (Fail Open)
        return response