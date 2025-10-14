# app/services/auth_service.py

from flask import current_app
from app.models import Verificacao
from app.services import biometrics_service

def authenticate_user(cpf: str, selfie_atual_bytes: bytes):
    """
    Orquestra o fluxo de autenticação transacional para um usuário existente.
    """
    logger = current_app.logger
    workflow_executado = {}
    status_geral = "APROVADO"

    # Passo 1: Encontrar a verificação de onboarding original do usuário pelo CPF.
    logger.info(f"AUTH_SERVICE: Buscando verificação original para o CPF: {cpf}")
    # Filtra por verificações de Pessoa Física (PF) que contenham o CPF nos dados de entrada.
    verificacao_original = Verificacao.query.filter(
        Verificacao.tipo_verificacao == 'PF',
        Verificacao.dados_entrada_json.contains(cpf)
    ).order_by(Verificacao.timestamp.desc()).first()

    if not verificacao_original or not verificacao_original.selfie_url:
        logger.warning(f"AUTH_SERVICE: Nenhuma verificação de onboarding com selfie encontrada para o CPF: {cpf}")
        return {
            "status_geral": "PENDENCIA",
            "workflow_executado": {
                "busca_usuario": {
                    "status": "FALHA",
                    "detalhes": "Usuário não encontrado ou sem selfie de onboarding para comparação."
                }
            }
        }

    selfie_onboarding_url = verificacao_original.selfie_url
    logger.info(f"AUTH_SERVICE: Selfie de onboarding encontrada: {selfie_onboarding_url}")
    workflow_executado["busca_usuario"] = {"status": "SUCESSO", "detalhes": "Selfie de onboarding localizada."}

    # Passo 2: Liveness Passivo na nova selfie.
    resultado_liveness_passivo = biometrics_service.check_liveness_passivo(selfie_atual_bytes)
    workflow_executado["liveness_passivo"] = resultado_liveness_passivo
    if resultado_liveness_passivo["status"] != "APROVADO":
        status_geral = "PENDENCIA"
        
    # Passo 3: Face Match (Selfie Atual vs. Selfie do Onboarding)
    # A função check_facematch espera bytes, mas para a foto original temos uma URL.
    # Em um sistema real, faríamos o download da selfie_onboarding_url para comparar.
    # Aqui, vamos simular essa comparação, passando a URL como se fosse a foto em base64.
    logger.info("AUTH_SERVICE: Simulando Face Match entre a selfie atual e a selfie do onboarding.")
    resultado_face_match = biometrics_service.check_facematch(selfie_onboarding_url, selfie_atual_bytes)
    workflow_executado["face_match_transacional"] = resultado_face_match
    if resultado_face_match["status"] != "APROVADO":
        status_geral = "PENDENCIA"

    return {"status_geral": status_geral, "workflow_executado": workflow_executado}