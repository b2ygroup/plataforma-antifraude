# app/models.py

import json
from datetime import datetime
from app import db # Garante que estamos a usar a instância correta do db

class Verificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_verificacao = db.Column(db.String(10), index=True)
    status_geral = db.Column(db.String(20), index=True)
    dados_entrada_json = db.Column(db.Text) 
    resultado_completo_json = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    doc_frente_url = db.Column(db.String(255))
    selfie_url = db.Column(db.String(255))
    dados_extra_json = db.Column(db.JSON, nullable=True)
    risk_score = db.Column(db.Integer, index=True, nullable=True)

    def __repr__(self):
        return f'<Verificação {self.id} [{self.tipo_verificacao}] - {self.status_geral}>'
    
    def set_dados_entrada(self, dados):
        self.dados_entrada_json = json.dumps(dados)
        
    def set_resultado_completo(self, resultado):
        if isinstance(resultado, dict):
            self.resultado_completo_json = json.dumps(resultado, indent=2)
        else:
            self.resultado_completo_json = str(resultado)