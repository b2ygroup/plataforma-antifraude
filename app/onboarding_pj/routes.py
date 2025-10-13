# app/onboarding_pj/routes.py

from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao
from app.services import pj_service # Importa o nosso novo serviço

bp = Blueprint('onboarding_pj', __name__)

@bp.route('/verificar', methods=['POST'])
def verificar_empresa():
    logger = current_app.logger
    
    dados = request.get_json()
    if not dados or 'cnpj' not in dados:
        logger.warning('Requisição de verificação de PJ recebida sem CNPJ.')
        return jsonify({"erro": "O campo 'cnpj' é obrigatório."}), 400

    cnpj_raw = dados['cnpj']
    # Limpa o CNPJ para usar nas APIs
    cnpj_limpo = ''.join(filter(str.isdigit, cnpj_raw))
    
    logger.info(f'Iniciando verificação para o CNPJ: {cnpj_limpo}')
    
    # Chama o serviço para orquestrar a verificação
    resultados_finais = pj_service.verify_company(cnpj_limpo)
    
    logger.info(f'Verificação para o CNPJ {cnpj_limpo} finalizada com status: {resultados_finais["status_geral"]}')

    # Salva o resultado no Banco de Dados
    try:
        nova_verificacao = Verificacao(
            tipo_verificacao='PJ',
            status_geral=resultados_finais["status_geral"]
        )
        nova_verificacao.set_dados_entrada({'cnpj': cnpj_raw})
        nova_verificacao.set_resultado_completo(resultados_finais)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f'Verificação do CNPJ {cnpj_limpo} salva no banco de dados com ID: {nova_verificacao.id}')
    except Exception as e:
        logger.error(f'Falha ao salvar verificação do CNPJ {cnpj_limpo} no banco de dados: {e}')
        db.session.rollback()

    return jsonify(resultados_finais), 200