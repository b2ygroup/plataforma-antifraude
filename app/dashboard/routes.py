# app/dashboard/routes.py

import json
from flask import render_template, jsonify
from app.dashboard import bp
from app.models import Verificacao

@bp.route('/dashboard')
def index():
    return render_template('dashboard.html', title='Dashboard de Verificações')

@bp.route('/api/verifications')
def get_verifications():
    verifications = Verificacao.query.order_by(Verificacao.timestamp.desc()).all()
    data = []
    for v in verifications:
        data.append({
            'id': v.id,
            'tipo': v.tipo_verificacao,
            'status': v.status_geral,
            'timestamp': v.timestamp.strftime('%d/%m/%Y %H:%M:%S'),
            'dados_completos': json.loads(v.resultado_completo_json),
            # --- RETORNANDO AS URLs DAS IMAGENS ---
            'doc_frente_url': v.doc_frente_url,
            'selfie_url': v.selfie_url
        })
    return jsonify(data)