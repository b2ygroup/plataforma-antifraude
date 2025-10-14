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

# ✅ NOVIDADE: Esta é a nova função de Face Match real com DeepFace.
def check_facematch_real(img1_bytes: bytes, img2_bytes: bytes) -> dict:
    """
    Compara duas imagens (bytes) usando a biblioteca DeepFace e retorna um score de semelhança.
    """
    logger = current_app.logger
    logger.info("Biometrics Service (Face Match Real): Iniciando comparação biométrica com DeepFace...")

    if not img1_bytes or len(img1_bytes) < 5000 or not img2_bytes or len(img2_bytes) < 5000:
        logger.warning("Face Match Real: Uma ou ambas as imagens são muito pequenas ou inválidas.")
        return {"status": "PENDENCIA", "motivo": "Imagem de referência ou selfie inválida.", "similaridade": 0, "threshold": 0}

    # DeepFace funciona com caminhos de arquivo, então salvamos os bytes em arquivos temporários.
    with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp1, \
         tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as tmp2:
        tmp1.write(img1_bytes)
        tmp2.write(img2_bytes)
        img1_path = tmp1.name
        img2_path = tmp2.name

    try:
        # A função verify da DeepFace retorna um dicionário com o resultado.
        # Usamos o modelo 'VGG-Face', um padrão de mercado robusto.
        result = DeepFace.verify(
            img1_path=img1_path,
            img2_path=img2_path,
            model_name='VGG-Face',
            enforce_detection=False # Não falha se um rosto não for detectado, apenas retorna 'verified': False
        )
        
        # O resultado 'distance' é a dissimilaridade. Quanto menor, mais parecidas são as faces.
        # Convertemos para uma 'similaridade' de 0 a 1 para facilitar o entendimento.
        distance = result.get('distance', 1.0)
        similaridade = 1 - distance
        
        # Definimos um limiar de confiança. Scores acima disso são considerados APROVADOS.
        # Este valor pode ser ajustado conforme a necessidade do negócio.
        threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.60) # 60% de similaridade
        
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
        # Garante que os arquivos temporários sejam sempre removidos.
        os.remove(img1_path)
        os.remove(img2_path)


def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    # A função de liveness passivo continua a mesma.
    logger = current_app.logger
    logger.info("Biometrics Service (Liveness Passivo): Iniciando verificação de sorriso...")

    try:
        if selfie_bytes.startswith(b"data:image"):
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
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado na selfie."}

        face = faces[0]
        # ... (resto da lógica de liveness)
        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0, vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2, vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }
        joy_score = likelihood_map.get(face.joy_likelihood, 0)
        if joy_score >= 3:
            return {"status": "APROVADO", "detalhes": "Sorriso detectado. Prova de vida aprovada."}
        else:
            return {"status": "PENDENCIA", "motivo": "Nenhum sorriso detectado."}

    except Exception as e:
        logger.error(f"Erro em check_liveness_passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha na análise de prova de vida."}