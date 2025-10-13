# app/models.py

import json
from datetime import datetime
from app import db

class Verificacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo_verificacao = db.Column(db.String(10), index=True)
    status_geral = db.Column(db.String(20), index=True)
    dados_entrada_json = db.Column(db.Text) 
    resultado_completo_json = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    # Colunas para as imagens principais
    doc_frente_url = db.Column(db.String(255))
    selfie_url = db.Column(db.String(255))

    # NOVIDADE: Coluna para guardar dados extras, como a URL da selfie com documento
    dados_extra_json = db.Column(db.JSON, nullable=True)

    def __repr__(self):
        return f'<Verificação {self.id} [{self.tipo_verificacao}] - {self.status_geral}>'
    
    def set_dados_entrada(self, dados):
        self.dados_entrada_json = json.dumps(dados)
        
    def set_resultado_completo(self, resultado):
        self.resultado_completo_json = json.dumps(resultado, indent=2)