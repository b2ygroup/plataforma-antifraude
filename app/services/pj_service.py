# app/services/pj_service.py

import requests
from flask import current_app

def _consultar_receita_federal(cnpj: str):
    """Consulta os dados de um CNPJ na BrasilAPI."""
    logger = current_app.logger
    try:
        url_receita = f"{current_app.config['BRASILAPI_BASE_URL']}{cnpj}"
        response = requests.get(url_receita, timeout=10)
        response.raise_for_status()
        dados_receita = response.json()
        logger.info(f'PJ_SERVICE: CNPJ {cnpj} encontrado na Receita Federal.')
        return {"status": "APROVADO", "dados": dados_receita}
    except requests.exceptions.HTTPError as e:
        logger.error(f'PJ_SERVICE: Erro ao consultar CNPJ {cnpj} na Receita: {e}')
        return {"status": "PENDENCIA", "erro": f"CNPJ não encontrado ou inválido. Detalhes: {str(e)}"}
    except Exception as e:
        logger.error(f'PJ_SERVICE: Erro inesperado ao consultar CNPJ {cnpj}: {e}')
        return {"status": "ERRO", "erro": f"Erro interno ao consultar Receita Federal: {str(e)}"}

def _simular_enriquecimento_qsa(dados_receita: dict):
    """Simula a busca pelo Quadro de Sócios e Administradores (QSA)."""
    logger = current_app.logger
    qsa_encontrado = dados_receita.get("qsa", [])
    if not qsa_encontrado:
        logger.info("PJ_SERVICE: Nenhum QSA encontrado nos dados da Receita, simulando busca externa.")
        # Simula a busca em uma fonte externa
        qsa_encontrado = [
            {"nome_socio": "LEONARDO ALMEIDA ALVES", "cpf_cnpj_socio": "123.456.789-00", "qualificacao_socio": "Sócio-Administrador"},
            {"nome_socio": "EMPRESA FICTICIA LTDA", "cpf_cnpj_socio": "00.111.222/0001-33", "qualificacao_socio": "Sócio"}
        ]
    
    logger.info(f"PJ_SERVICE: QSA encontrado com {len(qsa_encontrado)} membros.")
    return {"status": "APROVADO", "dados": qsa_encontrado}

def _simular_bgc_completo(cnpj: str, razao_social: str):
    """Simula um Background Check (BGC) completo com múltiplas fontes."""
    logger = current_app.logger
    logger.info(f"PJ_SERVICE: Simulando BGC completo para {razao_social}")

    detalhes = {
        "processos_tribunais_justica": "Nenhum processo encontrado." if int(cnpj[-2]) % 5 != 0 else "Encontrado 1 processo.",
        "processos_trf": "Nada consta.",
        "listas_internacionais_ofac_uk_ue_onu": "Nome não consta em listas restritivas." if "block" not in razao_social.lower() else "Nome consta na lista da OFAC.",
        "cnep": "Nada consta.",
        "cepim": "Nada consta."
    }

    status_geral_bgc = "APROVADO"
    if "Encontrado" in detalhes["processos_tribunais_justica"] or "consta na lista" in detalhes["listas_internacionais_ofac_uk_ue_onu"]:
        status_geral_bgc = "PENDENCIA"
    
    return {"status": status_geral_bgc, "detalhes": detalhes}

def verify_company(cnpj: str):
    """
    Orquestra o fluxo completo de verificação de Pessoa Jurídica (PJ).
    """
    workflow_executado = {}
    status_geral = "APROVADO"
    
    # Etapa 1: Receita Federal
    resultado_receita = _consultar_receita_federal(cnpj)
    workflow_executado["receita_federal"] = resultado_receita
    if resultado_receita["status"] != "APROVADO":
        # Se a consulta principal falhar, interrompe e retorna a pendência/erro.
        return {"status_geral": "PENDENCIA", "workflow_executado": workflow_executado}
    
    dados_empresa = resultado_receita.get("dados", {})
    razao_social = dados_empresa.get("razao_social", "")
    
    # Etapa 2: Enriquecimento / QSA
    resultado_qsa = _simular_enriquecimento_qsa(dados_empresa)
    workflow_executado["enriquecimento_qsa"] = resultado_qsa
    # Normalmente, uma falha aqui também geraria pendência, mas manteremos simples por enquanto.
    
    # Etapa 3: Background Check (BGC)
    resultado_bgc = _simular_bgc_completo(cnpj, razao_social)
    workflow_executado["background_check"] = resultado_bgc
    if resultado_bgc["status"] != "APROVADO":
        status_geral = "PENDENCIA"

    return {"status_geral": status_geral, "workflow_executado": workflow_executado}