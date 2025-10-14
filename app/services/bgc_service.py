# app/services/bgc_service.py
from flask import current_app
import random

def check_background(cpf: str, nome: str):
    """
    Simula um Background Check (BGC) detalhado, conforme o fluxo da proposta.
    """
    logger = current_app.logger
    logger.info(f"BGC_SERVICE: Simulando BGC detalhado para {nome}")

    # Em um cenário real, cada função faria uma chamada a uma API específica.
    def simular_antecedentes_criminais():
        return {"status": "APROVADO", "detalhes": "Nada consta"}

    def simular_listas_restritivas():
        # Simulando que o usuário não está em nenhuma lista
        return {"status": "APROVADO", "detalhes": {"OFAC": "OK", "ONU": "OK", "UK": "OK", "UE": "OK"}}

    def simular_mandados_de_prisao():
        return {"status": "APROVADO", "detalhes": "Nenhum mandado em aberto"}

    def simular_risco_contato():
        score = round(random.uniform(0.1, 0.5), 2)
        return {"status": "APROVADO", "detalhes": f"Score de risco para telefone/email/IP: {score}"}

    # Orquestra as sub-verificações
    resultados_bgc = {
        "antecedentes_criminais": simular_antecedentes_criminais(),
        "listas_restritivas": simular_listas_restritivas(),
        "mandados_de_prisao": simular_mandados_de_prisao(),
        "risco_dados_contato": simular_risco_contato(),
    }
    
    # Define o status geral do BGC. Se qualquer verificação falhar, o status geral será de pendência.
    status_geral_bgc = "APROVADO"
    for chave, resultado in resultados_bgc.items():
        if resultado["status"] != "APROVADO":
            status_geral_bgc = "PENDENCIA"
            break

    return {
        "status": status_geral_bgc,
        "detalhes": resultados_bgc
    }