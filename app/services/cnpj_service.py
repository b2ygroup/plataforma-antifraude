# app/services/cnpj_service.py
import requests
from datetime import datetime, timezone

def consultar_cnpj(cnpj_limpo: str):
    """
    Consulta um CNPJ na BrasilAPI e retorna os dados de forma estruturada.
    """
    try:
        brasil_api_url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(brasil_api_url, timeout=10)

        # Adiciona informações de diagnóstico no retorno
        consulta_info = {
            "fonte_dos_dados": "BrasilAPI",
            "data_consulta_utc": datetime.now(timezone.utc).isoformat()
        }

        if response.status_code == 200:
            dados_api = response.json()
            # Combina os dados da consulta com as informações de diagnóstico
            dados_api.update(consulta_info)
            return {"sucesso": True, "dados": dados_api}
        
        else:
            return {
                "sucesso": False, 
                "status_code": response.status_code,
                "erro": "CNPJ não encontrado ou serviço indisponível.",
                "detalhes": consulta_info
            }

    except requests.exceptions.RequestException as e:
        return {
            "sucesso": False,
            "erro": "Falha de comunicação com a API de consulta.",
            "detalhes": str(e)
        }