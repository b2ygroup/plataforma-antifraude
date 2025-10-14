# app/services/biometrics_service.py
import base64
import json
import tempfile
import os
from flask import current_app
from google.cloud import vision
from google.oauth2 import service_account
from deepface import DeepFace

def _get_vision_client():
    logger = current_app.logger
    google_creds_json_str = current_app.config.get('GOOGLE_CREDENTIALS_JSON') or None
    if google_creds_json_str:
        creds_dict = json.loads(google_creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = vision.ImageAnnotatorClient(credentials=credentials)
        logger.debug("Biometrics Service: Autenticado no Vision API via variável de ambiente.")
    else:
        client = vision.ImageAnnotatorClient()
        logger.debug("Biometrics Service: Autenticado no Vision API via configuração padrão.")
    return client

def check_facematch_real(img1_bytes: bytes, img2_bytes: bytes) -> dict:
    """
    Compara duas imagens (bytes) usando a biblioteca DeepFace e retorna um score de semelhança.
    """
    logger = current_app.logger
    logger.info("Biometrics Service (Face Match Real): Iniciando comparação biométrica com DeepFace...")

    if not img1_bytes or len(img1_bytes) < 5000 or not img2_bytes or len(img2_bytes) < 5000:
        logger.warning("Face Match Real: Uma ou ambas as imagens são muito pequenas ou inválidas.")
        return {"status": "PENDENCIA", "motivo": "Imagem de referência ou selfie inválida.", "similaridade": 0, "threshold": 0}

    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp1, \
         tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp2:
        tmp1.write(img1_bytes)
        tmp2.write(img2_bytes)
        img1_path = tmp1.name
        img2_path = tmp2.name

    try:
        result = DeepFace.verify(
            img1_path=img1_path,
            img2_path=img2_path,
            model_name='VGG-Face',
            enforce_detection=False
        )
        
        distance = result.get('distance', 1.0)
        similaridade = 1 - distance
        
        threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.60)
        
        status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
        
        logger.info(f"Face Match Real: similaridade={similaridade:.4f}, threshold={threshold:.2f}, status={status}")
        
        return {
            "status": status,
            "similaridade": similaridade,
            "threshold": threshold,
            "detalhes": f"Score de similaridade: {similaridade*100:.2f}%"
        }

    except Exception as e:
        logger.error(f"Erro durante a execução do DeepFace.verify: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha no serviço de biometria.", "similaridade": 0, "threshold": 0}

    finally:
        os.remove(img1_path)
        os.remove(img2_path)


# ✅ NOVIDADE: A função de Prova de Vida Passiva foi totalmente reescrita.
def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    """
    Realiza uma Prova de Vida Passiva aprimorada, verificando a qualidade da imagem
    e a presença de um único rosto claro, além do sorriso.
    """
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
        
        # 1. Validação de Rosto Único
        if not faces:
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado na selfie. Tente uma foto com boa iluminação."}
        if len(faces) > 1:
            return {"status": "REPROVADO", "motivo": f"Múltiplos rostos ({len(faces)}) detectados. A selfie deve conter apenas uma pessoa."}

        face = faces[0]
        
        # 2. Validação de Qualidade da Imagem
        confianca_deteccao = face.detection_confidence
        if confianca_deteccao < 0.85:
            return {"status": "REPROVADO", "motivo": f"O rosto não está nítido o suficiente (confiança: {confianca_deteccao:.2f}). Tente outra foto."}
        
        if face.under_exposed_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "A selfie está muito escura. Por favor, procure um local mais iluminado."}
            
        if face.blurred_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "A selfie está borrada. Por favor, mantenha a câmera estável."}

        if face.headwear_likelihood in [vision.Likelihood.LIKELY, vision.Likelihood.VERY_LIKELY]:
            return {"status": "REPROVADO", "motivo": "Acessórios como bonés ou chapéus que cobrem o rosto não são permitidos."}

        # 3. Validação de Prova de Vida (Sorriso)
        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0, vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2, vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }
        score_sorriso = likelihood_map.get(face.joy_likelihood, 0)
        
        if score_sorriso >= 3: # LIKELY ou VERY_LIKELY
            logger.info("Liveness Passivo v2: APROVADO. Rosto único, com boa qualidade e sorriso detectado.")
            return {"status": "APROVADO", "detalhes": "Selfie de alta qualidade e sorriso detectado. Prova de vida aprovada."}
        else:
            logger.warning("Liveness Passivo v2: PENDENCIA. Rosto de boa qualidade, mas sorriso não detectado.")
            return {"status": "PENDENCIA", "motivo": "Não foi possível detectar um sorriso claro. Por favor, tente novamente sorrindo para a câmera."}

    except Exception as e:
        logger.error(f"Erro inesperado em check_liveness_passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha na análise de prova de vida."}