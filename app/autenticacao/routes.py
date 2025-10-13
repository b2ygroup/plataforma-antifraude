# app/autenticacao/routes.py

from flask import request, jsonify, current_app
from app.autenticacao import bp
from app.services import auth_service
from app.decorators import require_api_key # NOVIDADE: Importa do novo local

@bp.route('/autenticar', methods=['POST'])
@require_api_key
def autenticar_transacao():
    """
    Recebe uma selfie e um CPF para autenticar um usuário existente.
    """
    logger = current_app.logger
    
    if 'selfie_atual' not in request.files or 'cpf' not in request.form:
        return jsonify({"erro": "Os campos 'selfie_atual' e 'cpf' são obrigatórios."}), 400

    cpf = request.form['cpf']
    selfie_file = request.files['selfie_atual']
    selfie_bytes = selfie_file.read()

    if not selfie_bytes:
        return jsonify({"erro": "O arquivo da selfie está vazio."}), 400

    logger.info(f"Iniciando fluxo de autenticação para o CPF: {cpf}")

    try:
        resultado = auth_service.authenticate_user(cpf, selfie_bytes)
        if resultado['status_geral'] != 'APROVADO':
            if resultado['workflow_executado'].get('busca_usuario', {}).get('status') == 'FALHA':
                return jsonify(resultado), 404
            return jsonify(resultado), 400

        return jsonify(resultado), 200
    except Exception as e:
        logger.error(f"Erro inesperado durante a autenticação: {e}", exc_info=True)
        return jsonify({"erro": "Ocorreu um erro interno no servidor."}), 500