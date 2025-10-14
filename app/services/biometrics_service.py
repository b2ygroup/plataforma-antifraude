# app/services/biometrics_service.py
import base64
import json
import os
import boto3
from flask import current_app
from google.cloud import vision
from google.oauth2 import service_account

def _get_vision_client():
    """Inicializa e retorna o cliente da Google Vision API."""
    logger = current_app.logger
    google_creds_json_str = current_app.config.get('GOOGLE_CREDENTIALS_JSON') or os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if google_creds_json_str:
        creds_dict = json.loads(google_creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        logger.debug("Biometrics Service: Autenticado no Vision API.")
    else:
        client = vision.ImageAnnotatorClient()
        logger.debug("Biometrics Service: Autenticado no Vision API via configuração padrão.")
    return client

def check_facematch_real(img1_bytes: bytes, img2_bytes: bytes) -> dict:
    """
    Compara duas faces usando o Amazon Rekognition.
    img1_bytes: Foto de referência (ex: do documento).
    img2_bytes: Foto a ser comparada (ex: da selfie).
    """
    logger = current_app.logger
    logger.info("Biometrics Service (AWS Rekognition): Iniciando comparação biométrica...")

    if not img1_bytes or not img2_bytes:
        logger.warning("Rekognition: Uma ou ambas as imagens estão vazias.")
        return {"status": "PENDENCIA", "motivo": "Imagem de referência ou selfie inválida.", "similaridade": 0, "threshold": 0.9}

    try:
        # Pega as credenciais das variáveis de ambiente
        aws_access_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
        aws_region = os.environ.get('AWS_REGION', 'us-east-1')

        if not all([aws_access_key, aws_secret_key]):
            logger.error("Credenciais da AWS não configuradas nas variáveis de ambiente.")
            return {"status": "ERRO", "motivo": "Serviço de biometria não configurado no servidor."}

        rekognition_client = boto3.client(
            'rekognition',
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            region_name=aws_region
        )

        response = rekognition_client.compare_faces(
            SourceImage={'Bytes': img1_bytes},
            TargetImage={'Bytes': img2_bytes},
            SimilarityThreshold=0  # Pegamos todos os resultados e aplicamos nosso limiar depois
        )
        
        if not response['FaceMatches']:
            logger.warning("Rekognition: Nenhuma face correspondente encontrada.")
            return {"status": "PENDENCIA", "similaridade": 0, "threshold": 0.9, "detalhes": "Nenhuma correspondência facial encontrada."}

        # A AWS retorna a similaridade de 0 a 100
        similaridade_aws = response['FaceMatches'][0]['Similarity']
        similaridade = similaridade_aws / 100.0
        
        threshold = 0.90  # Limiar de 90% de similaridade, um padrão de mercado para alta confiança
        status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
        
        logger.info(f"Rekognition Face Match: similaridade={similaridade:.4f}, threshold={threshold:.2f}, status={status}")
        
        return {
            "status": status,
            "similaridade": similaridade,
            "threshold": threshold,
            "detalhes": f"Score de similaridade: {similaridade*100:.2f}%"
        }

    except rekognition_client.exceptions.InvalidParameterException:
        logger.warning("Rekognition: Nenhuma face detectada em uma das imagens.")
        return {"status": "PENDENCIA", "motivo": "Não foi possível detectar um rosto em uma das imagens."}
    except Exception as e:
        logger.error(f"Erro inesperado ao chamar a AWS Rekognition: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha no serviço de biometria."}


def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    """Realiza uma Prova de Vida Passiva aprimorada, usando a Google Vision API."""
    logger = current_app.logger
    logger.info("Biometrics Service (Liveness Passivo v2): Iniciando verificação aprimorada...")
    try:
        if selfie_bytes.startswith(b"data:image"):
            header, b64data = selfie_bytes.split(b",", 1)
            selfie_bytes = base64.b64decode(b64data)

        if len(selfie_bytes) < 5000:
            return {"status": "REPROVADO", "motivo": "Selfie muito pequena ou inválida."}

        client = _get_vision_client()
        image = vision.Image(content=selfie_bytes)
        response = client.face_detection(image=image)

        if response.error.message:
            logger.error(f"Erro Vision API em Liveness Passivo: {response.error.message}")
            return {"status": "ERRO", "motivo": response.error.message}

        faces = response.face_annotations
        
        if not faces:
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado na selfie. Tente uma foto com boa iluminação."}
        if len(faces) > 1:
            return {"status": "REPROVADO", "motivo": f"Múltiplos rostos ({len(faces)}) detectados. A selfie deve conter apenas uma pessoa."}

        face = faces[0]
        
        confianca_deteccao = face.detection_confidence
        if confianca_deteccao < 0.85:
            return {"status": "REPROVADO", "motivo": f"O rosto não está nítido o suficiente (confiança: {confianca_deteccao:.2f}). Tente outra foto."}
        
        if face.under_exposed_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "A selfie está muito escura. Por favor, procure um local mais iluminado."}
            
        if face.blurred_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "A selfie está borrada. Por favor, mantenha a câmera estável."}

        if face.headwear_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "Acessórios como bonés ou chapéus que cobrem o rosto não são permitidos."}

        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0, vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2, vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }
        score_sorriso = likelihood_map.get(face.joy_likelihood, 0)
        
        if score_sorriso >= 3:
            logger.info("Liveness Passivo v2: APROVADO. Rosto único, com boa qualidade e sorriso detectado.")
            return {"status": "APROVADO", "detalhes": "Selfie de alta qualidade e sorriso detectado. Prova de vida aprovada."}
        else:
            logger.warning("Liveness Passivo v2: PENDENCIA. Rosto de boa qualidade, mas sorriso não detectado.")
            return {"status": "PENDENCIA", "motivo": "Não foi possível detectar um sorriso claro. Por favor, tente novamente sorrindo para a câmera."}

    except Exception as e:
        logger.error(f"Erro inesperado em check_liveness_passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha na análise de prova de vida."}