# app/dashboard/routes.py

import json
from flask import render_template, jsonify, current_app
from app.dashboard import bp
from app.models import Verificacao

@bp.route('/dashboard')
def index():
    """
    Renderiza a página principal do Dashboard Administrativo.
    """
    return render_template('dashboard.html', title='Dashboard de Verificações')

@bp.route('/api/verifications')
def get_verifications():
    """
    API interna que busca todas as verificações no banco de dados
    e as retorna em formato JSON para o frontend.
    """
    logger = current_app.logger
    verifications = Verificacao.query.order_by(Verificacao.timestamp.desc()).all()
    
    data = []
    for v in verifications:
        try:
            # Tenta carregar o JSON. Se falhar, pula para o próximo registro.
            dados_completos = json.loads(v.resultado_completo_json)
            
            data.append({
                'id': v.id,
                'tipo': v.tipo_verificacao,
                'status': v.status_geral,
                'timestamp': v.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
                'dados_completos': dados_completos,
                'doc_frente_url': v.doc_frente_url,
                'selfie_url': v.selfie_url
            })
        except json.JSONDecodeError:
            logger.error(f"Erro de JSON: Não foi possível processar o registro de verificação com ID {v.id}. O JSON salvo está malformado.")
            # Continua para o próximo item do loop, ignorando o registro quebrado.
            continue
            
    return jsonify(data)