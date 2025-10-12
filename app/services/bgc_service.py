# app/services/bgc_service.py
import os
import requests
from flask import current_app

def check_background(cpf: str, nome: str) -> dict:
    """
    Função REAL para chamar uma API externa de Background Check (BGC).
    Este é um exemplo que você adaptará para o fornecedor que contratar.
    """
    logger = current_app.logger
    api_key = os.environ.get('BGC_PROVIDER_API_KEY')
    api_url = 'https://api.fornecedorbgc.com/v2/consultas' # Exemplo de URL

    if not api_key:
        logger.error("BGC Service: A chave de API do fornecedor de BGC não foi configurada.")
        return {"status": "ERRO_CONFIGURACAO", "detalhes": "API de BGC não configurada no servidor."}

    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    payload = {
        'cpf': cpf,
        'nome': nome,
        'consultas': [
            'antecedentes_criminais',
            'listas_restritivas',
            'mandados_prisao'
        ]
    }
    
    logger.info(f"BGC Service: Realizando consulta para o CPF {cpf} no fornecedor externo.")
    
    try:
        response = requests.post(api_url, headers=headers, json=payload, timeout=30)
        response.raise_for_status() # Lança um erro para respostas 4xx ou 5xx
        
        # Aqui, você processaria a resposta real do fornecedor
        # e a traduziria para o formato que nossa plataforma entende.
        data = response.json()
        
        # Exemplo de tradução da resposta
        status_final_bgc = "APROVADO"
        if data.get('mandados_prisao_encontrados') > 0:
            status_final_bgc = "PENDENCIA"

        logger.info(f"BGC Service: Consulta para CPF {cpf} retornou status: {status_final_bgc}")
        return {"status": status_final_bgc, "detalhes": data}

    except requests.exceptions.RequestException as e:
        logger.error(f"BGC Service: Erro de comunicação com a API de BGC: {e}")
        return {"status": "ERRO_COMUNICACAO", "detalhes": str(e)}