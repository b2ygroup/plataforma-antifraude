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
    try:
        verifications = Verificacao.query.order_by(Verificacao.timestamp.desc()).all()
        
        data = []
        for v in verifications:
            try:
                dados_completos = json.loads(v.resultado_completo_json) if v.resultado_completo_json else {}
                timestamp_str = v.timestamp.strftime('%d/%m/%Y %H:%M:%S') if v.timestamp else 'Data indisponível'
                dados_extra = v.dados_extra_json if v.dados_extra_json else {}

                data.append({
                    'id': v.id,
                    'tipo': v.tipo_verificacao,
                    'status': v.status_geral,
                    'timestamp': timestamp_str,
                    'dados_completos': dados_completos,
                    'doc_frente_url': v.doc_frente_url,
                    'selfie_url': v.selfie_url,
                    'dados_extra': dados_extra
                })
            except Exception as e:
                logger.error(f"Erro ao processar o registo de verificação com ID {v.id}: {e}")
                continue
                
        return jsonify(data)
        
    except Exception as e:
        # NOVIDADE: Retorna a mensagem de erro específica para o frontend
        logger.error(f"Erro 500 na API /api/verifications. Detalhes: {e}", exc_info=True)
        return jsonify({"erro": f"Ocorreu um erro interno no servidor: {str(e)}"}), 500