# app/services/biometrics_service.py
import random
from flask import current_app

def check_facematch(foto_doc_base64: str, selfie_bytes: bytes) -> dict:
    """
    Em produção, esta função chamaria uma API real de Face Match.
    Por enquanto, ela mantém nossa simulação inteligente.
    """
    logger = current_app.logger
    logger.debug("Biometrics Service (Face Match): Comparando biometria facial...")
    
    if not foto_doc_base64 or len(foto_doc_base64) < 100:
        similaridade = 0.10
    else:
        similaridade = random.uniform(0.90, 0.99)
    
    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
    
    return {"status": status, "similaridade": similaridade, "threshold": threshold}

def check_liveness_ativo() -> dict:
    """
    Em produção, esta função validaria o desafio de prova de vida.
    """
    return {"status": "APROVADO", "detalhes": "Desafios de prova de vida completados com sucesso."}

def check_liveness_passivo(selfie_bytes: bytes) -> dict:
    """
    Em produção, esta função chamaria uma API real de Liveness Passivo.
    """
    return {"status": "APROVADO", "detalhes": "Nenhum sinal de ataque detectado no arquivo."}