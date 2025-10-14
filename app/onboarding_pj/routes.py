# app/onboarding_pj/routes.py
import os
import requests
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from app import db
# from app.models import Verificacao # Descomente se for salvar verificações de PJ no DB

# ✅ Novo Blueprint exclusivamente para PJ, com o nome correto.
bp = Blueprint('onboarding_pj', __name__)

# Função de segurança para a chave de API (mantida do seu código original)
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.environ.get('PLATFORM_API_KEY')
        if not api_key:
            current_app.logger.error("A autenticação de API não está configurada no servidor (PLATFORM_API_KEY não encontrada).")
            return jsonify({"erro": "A autenticação de API não está configurada no servidor."}), 500
        
        if request.headers.get('X-API-KEY') and request.headers.get('X-API-KEY') == api_key:
            return f(*args, **kwargs)
        else:
            current_app.logger.warning("Tentativa de acesso não autorizado: Chave de API inválida ou não fornecida.")
            return jsonify({"erro": "Chave de API inválida ou não fornecida."}), 401
    return decorated_function

# Função para formatar o resultado da API no padrão que o seu frontend espera
def formatar_resultado_cnpj(api_data):
    # Traduz e seleciona os campos mais importantes da BrasilAPI
    dados_formatados = {
        "cnpj_consultado": api_data.get("cnpj"),
        "razao_social": api_data.get("razao_social"),
        "nome_fantasia": api_data.get("nome_fantasia"),
        "situacao_cadastral": api_data.get("descricao_situacao_cadastral"),
        "data_abertura": api_data.get("data_inicio_atividade"),
        "capital_social": f"R$ {api_data.get('capital_social'):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
        "endereco": f"{api_data.get('logradouro')}, {api_data.get('numero')} - {api_data.get('bairro')}, {api_data.get('municipio')} - {api_data.get('uf')}, CEP: {api_data.get('cep')}",
        "atividade_principal": api_data.get("cnae_fiscal_descricao"),
        "socios": api_data.get("qsa") # Quadro de Sócios e Administradores
    }

    status_workflow = "APROVADO" if dados_formatados["situacao_cadastral"] == "ATIVA" else "PENDENCIA"
    
    return {
        "status_geral": status_workflow,
        "workflow_executado": {
            "consulta_cnpj_receita": {
                "status": status_workflow,
                "dados": dados_formatados
            }
        }
    }

@bp.route('/verificar', methods=['POST'])
@require_api_key
def verificar_empresa():
    logger = current_app.logger
    
    # 1. Recebe o CNPJ do frontend (via JSON)
    data = request.get_json()
    if not data or 'cnpj' not in data:
        logger.warning("Requisição para verificar PJ recebida sem o campo 'cnpj'.")
        return jsonify({"erro": "O campo 'cnpj' é obrigatório."}), 400

    cnpj_raw = data.get('cnpj', '')
    # Limpa o CNPJ para enviar à API (somente números)
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj_raw))
    
    if len(cnpj_limpo) != 14:
        return jsonify({"erro": "O CNPJ fornecido é inválido."}), 400
        
    logger.info(f"Iniciando consulta real para o CNPJ: {cnpj_limpo}")

    try:
        # 2. Faz a chamada REAL para a BrasilAPI
        brasil_api_url = f"https://brasilapi.com.br/api/cnpj/v1/{cnpj_limpo}"
        response = requests.get(brasil_api_url, timeout=10) # Timeout de 10 segundos

        # 3. Trata a resposta da API
        if response.status_code == 200:
            dados_cnpj = response.json()
            resultado_formatado = formatar_resultado_cnpj(dados_cnpj)
            logger.info(f"CNPJ {cnpj_limpo} consultado com sucesso.")
            return jsonify(resultado_formatado), 200
        elif response.status_code == 404:
            logger.warning(f"CNPJ {cnpj_limpo} não encontrado na base da Receita Federal.")
            return jsonify({"erro": "CNPJ não encontrado."}), 404
        else:
            logger.error(f"Erro da BrasilAPI ao consultar o CNPJ {cnpj_limpo}. Status: {response.status_code}, Resposta: {response.text}")
            return jsonify({"erro": "O serviço de consulta de CNPJ está indisponível no momento. Tente novamente mais tarde."}), 503

    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de comunicação com a BrasilAPI para o CNPJ {cnpj_limpo}: {e}", exc_info=True)
        return jsonify({"erro": "Não foi possível conectar ao serviço de consulta de CNPJ."}), 500
    except Exception as e:
        logger.error(f"Erro inesperado durante a verificação de PJ para o CNPJ {cnpj_limpo}: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro interno ao processar a verificação do CNPJ."}), 500