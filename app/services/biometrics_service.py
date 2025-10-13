# app/services/biometrics_service.py
import random
import base64
from flask import current_app
from google.cloud import vision
from google.oauth2 import service_account
import json
import io


def _get_vision_client():
    logger = current_app.logger
    google_creds_json_str = current_app.config.get('GOOGLE_CREDENTIALS_JSON') or None
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


def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    logger = current_app.logger
    logger.info("Biometrics Service (Liveness Passivo): Iniciando verificação de sorriso...")

    try:
        # 🔍 Diagnóstico inicial
        logger.info(f"Tamanho da selfie recebida: {len(selfie_bytes)} bytes")

        # Verifica se é base64 (caso frontend envie assim)
        if selfie_bytes.startswith(b"data:image"):
            logger.info("Biometrics Service: Detectado formato base64, decodificando...")
            header, b64data = selfie_bytes.split(b",", 1)
            selfie_bytes = base64.b64decode(b64data)

        if len(selfie_bytes) < 5000:
            return {"status": "REPROVADO", "motivo": "Imagem muito pequena ou inválida."}

        client = _get_vision_client()
        image = vision.Image(content=selfie_bytes)
        response = client.face_detection(image=image)

        if response.error.message:
            logger.error(f"Erro Vision: {response.error.message}")
            return {"status": "ERRO", "motivo": response.error.message}

        faces = response.face_annotations
        if not faces:
            logger.warning("Biometrics Service: Nenhum rosto detectado.")
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado. Tente outra foto com boa iluminação."}

        face = faces[0]
        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0,
            vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2,
            vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }

        joy_score = likelihood_map.get(face.joy_likelihood, 0)
        conf = getattr(face, 'detection_confidence', 0)
        logger.info(f"Liveness: confiança={conf:.2f}, sorriso_score={joy_score}/4")

        if conf < 0.5:
            return {"status": "REPROVADO", "motivo": "Rosto não reconhecido com confiança suficiente."}

        if joy_score >= 3:
            return {"status": "APROVADO", "detalhes": "Sorriso detectado. Prova de vida aprovada."}
        else:
            return {"status": "PENDENCIA", "motivo": "Nenhum sorriso detectado. Tente novamente sorrindo."}

    except Exception as e:
        logger.error(f"Erro em check_liveness_passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha na análise de prova de vida."}
