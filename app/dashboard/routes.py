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
    # --- MELHOR PRÁTICA ADICIONADA ---
    # Garante que estamos dentro do contexto da aplicação Flask para realizar
    # operações de banco de dados, o que é mais seguro em ambientes serverless.
    with current_app.app_context():
        # Busca todas as verificações, ordenando das mais recentes para as mais antigas
        verifications = Verificacao.query.order_by(Verificacao.timestamp.desc()).all()
        
        # Formata os dados para serem enviados como JSON
        data = []
        for v in verifications:
            data.append({
                'id': v.id,
                'tipo': v.tipo_verificacao,
                'status': v.status_geral,
                'timestamp': v.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
                'dados_completos': json.loads(v.resultado_completo_json),
                'doc_frente_url': v.doc_frente_url,
                'selfie_url': v.selfie_url
            })
            
    return jsonify(data)