# app/services/biometrics_service.py
import random
import base64
from flask import current_app
from google.cloud import vision
from google.oauth2 import service_account
import json
import io


def _get_vision_client():
    """Autentica no Google Vision, igual ao OCR."""
    logger = current_app.logger
    google_creds_json_str = current_app.config.get('GOOGLE_CREDENTIALS_JSON') or \
                            current_app.config.get('GOOGLE_APPLICATION_CREDENTIALS_JSON') or \
                            None
    if google_creds_json_str:
        creds_dict = json.loads(google_creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        logger.debug("Biometrics Service: Autenticado via variável de ambiente.")
    else:
        client = vision.ImageAnnotatorClient()
        logger.debug("Biometrics Service: Autenticado via configuração padrão.")
    return client


def check_facematch(foto_doc_base64: str, selfie_bytes: bytes) -> dict:
    """
    Simulação de Face Match. Em produção, chamaria uma API real (AWS Rekognition, FaceTec, etc.).
    """
    logger = current_app.logger
    logger.debug("Biometrics Service (Face Match): Comparando biometria facial...")

    if not foto_doc_base64 or len(foto_doc_base64) < 100 or not selfie_bytes:
        similaridade = 0.10
    else:
        similaridade = random.uniform(0.90, 0.99)

    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"

    logger.info(f"Face Match: similaridade={similaridade:.2f} threshold={threshold} status={status}")
    return {"status": status, "similaridade": similaridade, "threshold": threshold}


def check_liveness_ativo() -> dict:
    """
    Em produção, esta função validaria o desafio ativo (movimento, piscada etc.).
    """
    return {"status": "APROVADO", "detalhes": "Desafios de prova de vida completados com sucesso."}


def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    """
    Verifica se há um rosto e expressão de sorriso usando Google Vision API.
    Retorna APROVADO se um rosto real e sorriso forem detectados.
    """
    logger = current_app.logger
    logger.debug("Biometrics Service (Liveness Passivo): Iniciando análise facial...")

    if not selfie_bytes or len(selfie_bytes) < 2000:
        logger.warning("Biometrics Service: Selfie vazia ou inválida recebida.")
        return {"status": "REPROVADO", "motivo": "Imagem inválida ou corrompida."}

    try:
        client = _get_vision_client()
        image = vision.Image(content=selfie_bytes)
        response = client.face_detection(image=image)

        if response.error.message:
            logger.error(f"Erro no Vision API: {response.error.message}")
            return {"status": "ERRO", "motivo": response.error.message}

        faces = response.face_annotations
        if not faces:
            logger.warning("Biometrics Service: Nenhum rosto detectado na selfie.")
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado."}

        face = faces[0]
        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0,
            vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2,
            vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }

        joy_score = likelihood_map.get(face.joy_likelihood, 0)
        detection_confidence = getattr(face, 'detection_confidence', 0)
        logger.info(f"Liveness: joy={joy_score}/4 confiança={detection_confidence:.2f}")

        if detection_confidence < 0.5:
            return {"status": "REPROVADO", "motivo": "Rosto com baixa confiança na detecção."}

        if joy_score >= 3:
            logger.info("Biometrics Service: Sorriso detectado. Liveness aprovado.")
            return {"status": "APROVADO", "detalhes": "Sorriso detectado. Rosto real identificado."}
        else:
            logger.warning("Biometrics Service: Nenhum sorriso detectado.")
            return {"status": "PENDENCIA", "motivo": "Sorriso não identificado. Tente novamente sorrindo."}

    except Exception as e:
        logger.error(f"Erro inesperado em Liveness Passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha na análise facial."}
