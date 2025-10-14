# app/services/biometrics_service.py
import random
import base64
from flask import current_app
from google.cloud import vision
from google.oauth2 import service_account
import json
import io
import os # Importe o OS para salvar arquivos de debug

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
    # ... (sua função de facematch permanece a mesma)
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
    logger.info("Biometrics Service (Liveness Passivo): Iniciando verificação de prova de vida.")

    try:
        # 1. LOG INICIAL: Verifique o tipo e o início dos dados recebidos
        logger.info(f"Tamanho da selfie recebida: {len(selfie_bytes)} bytes")
        logger.debug(f"Tipo do dado recebido: {type(selfie_bytes)}")
        logger.debug(f"Início dos dados (primeiros 50 bytes): {selfie_bytes[:50]}")

        # 2. DECODIFICAÇÃO (seu código já está bom aqui)
        if selfie_bytes.startswith(b"data:image"):
            logger.info("Biometrics Service: Detectado formato base64, decodificando...")
            try:
                header, b64data = selfie_bytes.split(b",", 1)
                selfie_bytes = base64.b64decode(b64data)
                logger.info(f"Tamanho da imagem após decodificação: {len(selfie_bytes)} bytes")
            except Exception as e:
                logger.error(f"Erro ao decodificar base64: {e}")
                return {"status": "ERRO", "motivo": "A imagem enviada (base64) é inválida."}
        
        # 3. VERIFICAÇÃO DE TAMANHO MÍNIMO
        if len(selfie_bytes) < 5000: # 5KB é um bom valor mínimo
            logger.warning(f"Imagem recusada por ser muito pequena ({len(selfie_bytes)} bytes).")
            return {"status": "REPROVADO", "motivo": "Imagem muito pequena ou inválida."}
        
        # ---> SUGESTÃO DE DEBUG: Salve a imagem para análise manual <---
        # Crie uma pasta 'debug_images' na raiz do seu projeto.
        # Descomente as linhas abaixo para salvar cada selfie recebida.
        # debug_path = "debug_images"
        # if not os.path.exists(debug_path):
        #     os.makedirs(debug_path)
        # with open(os.path.join(debug_path, f"selfie_{random.randint(1000,9999)}.jpg"), "wb") as f:
        #     f.write(selfie_bytes)

        # 4. CHAMADA À API
        client = _get_vision_client()
        image = vision.Image(content=selfie_bytes)
        response = client.face_detection(image=image)
        
        # 5. LOG DETALHADO DA RESPOSTA DA API
        if response.error.message:
            logger.error(f"Erro na API Google Vision: {response.error.message}")
            return {"status": "ERRO", "motivo": response.error.message}
        
        # LOG da resposta completa para entender o que o Google está vendo
        logger.debug(f"Resposta completa do Google Vision: {response}")

        faces = response.face_annotations
        if not faces:
            logger.warning("Biometrics Service: Nenhum rosto detectado na imagem pela API.")
            return {"status": "REPROVADO", "motivo": "Nenhum rosto detectado. Tente outra foto com boa iluminação e sem acessórios."}

        # 6. ANÁLISE DO ROSTO (seu código já está bom aqui)
        face = faces[0]
        likelihood_map = {
            vision.Likelihood.VERY_UNLIKELY: 0, vision.Likelihood.UNLIKELY: 1,
            vision.Likelihood.POSSIBLE: 2, vision.Likelihood.LIKELY: 3,
            vision.Likelihood.VERY_LIKELY: 4
        }

        joy_score = likelihood_map.get(face.joy_likelihood, 0)
        conf = getattr(face, 'detection_confidence', 0)
        logger.info(f"Liveness: Confiança de detecção={conf:.2f}, Score de sorriso={joy_score}/4")

        # Ajuste no threshold de confiança pode ajudar
        if conf < 0.65: # Talvez aumentar um pouco o threshold para garantir qualidade
            return {"status": "REPROVADO", "motivo": f"Rosto detectado com baixa confiança ({conf:.2f}). Tente uma foto mais nítida."}

        if joy_score >= 3: # LIKELY ou VERY_LIKELY
            return {"status": "APROVADO", "detalhes": "Sorriso detectado. Prova de vida aprovada."}
        else:
            return {"status": "PENDENCIA", "motivo": "Não foi possível detectar um sorriso claro. Por favor, tente novamente sorrindo para a câmera."}

    except Exception as e:
        logger.error(f"Erro inesperado em check_liveness_passivo: {e}", exc_info=True)
        return {"status": "ERRO", "motivo": "Falha interna na análise de prova de vida."}