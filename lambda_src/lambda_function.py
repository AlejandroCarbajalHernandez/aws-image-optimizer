import json
import base64
from io import BytesIO
from PIL import Image
import boto3

s3_client = boto3.client('s3')

def lambda_handler(event, context):
    request = event['Records'][0]['cf']['request']
    response = event['Records'][0]['cf']['response']
    headers = request['headers']

    # Funcion auxiliar para inyectar headers de debug
    def add_debug_header(res, message):
        res['headers']['x-debug-reason'] = [{'key': 'X-Debug-Reason', 'value': message}]
        return res

    # 1. Validación de Status original
    if int(response['status']) >= 400:
        return add_debug_header(response, f"Original Status {response['status']}")

    # 2. Detectar Bucket
    try:
        s3_domain = request['origin']['s3']['domainName']
        bucket_name = s3_domain.split('.')[0]
    except KeyError:
        return add_debug_header(response, "No S3 Origin Detected")

    # 3. Verificar si pide WebP
    accept_webp = False
    if 'accept' in headers:
        for header in headers['accept']:
            if 'image/webp' in header['value']:
                accept_webp = True
                break
    
    if not accept_webp:
        # AQUI PUEDE ESTAR EL PROBLEMA: CloudFront no nos pasó el header Accept
        return add_debug_header(response, "Client did not send Accept: image/webp")

    try:
        # 4. Obtener imagen de S3
        key = request['uri'].lstrip('/')
        s3_response = s3_client.get_object(Bucket=bucket_name, Key=key)
        image_data = s3_response['Body'].read()

        # 5. Convertir
        img = Image.open(BytesIO(image_data))
        buffer = BytesIO()
        img.save(buffer, format="WEBP", quality=80)
        
        buffer.seek(0)
        img_str = base64.b64encode(buffer.getvalue()).decode('utf-8')
        
        # 6. Validar tamaño (Limite 1.3MB)
        if len(img_str) > 1300000:
            return add_debug_header(response, "Generated image too big (>1.3MB)")

        # 7. ÉXITO
        response['status'] = '200'
        response['statusDescription'] = 'OK'
        response['body'] = img_str
        response['bodyEncoding'] = 'base64'
        response['headers']['content-type'] = [{'key': 'Content-Type', 'value': 'image/webp'}]
        response['headers']['x-debug-reason'] = [{'key': 'X-Debug-Reason', 'value': 'Success: Converted to WebP'}]
        
        return response

    except Exception as e:
        print(f"Error: {str(e)}")
        # AQUI VEREMOS LA EXCEPCION REAL EN EL NAVEGADOR
        return add_debug_header(response, f"Error: {str(e)}")