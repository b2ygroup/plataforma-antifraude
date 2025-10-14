# app/onboarding_pj/routes.py
import os
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from app.services import cnpj_service # ✅ NOVIDADE: Importa nosso novo serviço

bp = Blueprint('onboarding_pj', __name__)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.environ.get('PLATFORM_API_KEY')
        if not api_key:
            return jsonify({"erro": "A autenticação de API não está configurada no servidor."}), 500
        if request.headers.get('X-API-KEY') and request.headers.get('X-API-KEY') == api_key:
            return f(*args, **kwargs)
        else:
            return jsonify({"erro": "Chave de API inválida ou não fornecida."}), 401
    return decorated_function

def formatar_resultado_cnpj(api_data):
    # A lógica de formatação continua a mesma, mas agora recebe os dados do nosso serviço
    status_receita = api_data.get("descricao_situacao_cadastral", "DESCONHECIDA")
    # ✅ LÓGICA CORRETA: Se a situação é ATIVA, o status é APROVADO.
    status_map = {
        "ATIVA": "APROVADO"
    }
    # Qualquer status diferente de "ATIVA" resultará em "PENDENCIA".
    status_workflow = status_map.get(status_receita, "PENDENCIA")

    try:
        capital_formatado = f"R$ {float(api_data.get('capital_social', 0)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (ValueError, TypeError):
        capital_formatado = "Não informado"

    dados_formatados = {
        "fonte_dos_dados": api_data.get("fonte_dos_dados"), # ✅ NOVIDADE
        "data_da_consulta": api_data.get("data_consulta_utc"), # ✅ NOVIDADE
        "cnpj_consultado": api_data.get("cnpj"),
        "razao_social": api_data.get("razao_social"),
        "nome_fantasia": api_data.get("nome_fantasia"),
        "situacao_cadastral_receita": status_receita,
        "data_abertura": api_data.get("data_inicio_atividade"),
        "porte_da_empresa": api_data.get("descricao_porte"),
        "natureza_juridica": api_data.get("natureza_juridica"),
        "capital_social": capital_formatado,
        "atividade_principal": api_data.get("cnae_fiscal_descricao"),
        "endereco_completo": f"{api_data.get('logradouro', '')}, {api_data.get('numero', '')} - {api_data.get('bairro', '')}, {api_data.get('municipio', '')} - {api_data.get('uf', '')}, CEP: {api_data.get('cep', '')}",
        "telefone": f"({api_data.get('ddd_telefone_1', '')}) {api_data.get('telefone1', 'Não informado')}",
        "email": api_data.get("email", "Não informado"),
        "quadro_de_socios_e_administradores": api_data.get("qsa")
    }
    
    return {
        "status_geral": status_workflow,
        "workflow_executado": { "consulta_cnpj_receita": { "status": status_workflow, "dados": dados_formatados } }
    }

@bp.route('/verificar', methods=['POST'])
@require_api_key
def verificar_empresa():
    logger = current_app.logger
    data = request.get_json()
    if not data or 'cnpj' not in data:
        return jsonify({"erro": "O campo 'cnpj' é obrigatório."}), 400

    cnpj_limpo = ''.join(filter(str.isdigit, data.get('cnpj', '')))
    if len(cnpj_limpo) != 14:
        return jsonify({"erro": "O CNPJ fornecido é inválido."}), 400
        
    logger.info(f"Iniciando consulta para o CNPJ: {cnpj_limpo} via cnpj_service")
    
    # ✅ NOVIDADE: A rota agora chama o serviço, mantendo-se limpa e focus.
    resultado = cnpj_service.consultar_cnpj(cnpj_limpo)
    
    if resultado["sucesso"]:
        dados_formatados = formatar_resultado_cnpj(resultado["dados"])
        return jsonify(dados_formatados), 200
    else:
        # Retorna o erro que o serviço identificou
        return jsonify({"erro": resultado["erro"], "detalhes": resultado.get("detalhes")}), resultado.get("status_code", 500)