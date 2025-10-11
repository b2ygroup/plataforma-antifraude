# app/models.py
import json
from datetime import datetime
from app import db

class Verificacao(db.Model):
    """
    Modelo do Banco de Dados para armazenar o resultado de cada verificação.
    Isso cria a tabela 'verificacao' no nosso banco de dados.
    """
    id = db.Column(db.Integer, primary_key=True)
    tipo_verificacao = db.Column(db.String(10), index=True) # 'PJ' ou 'PF'
    status_geral = db.Column(db.String(20), index=True) # 'APROVADO' ou 'PENDENCIA'
    
    # Armazenaremos os JSONs como texto.
    dados_entrada_json = db.Column(db.Text) 
    resultado_completo_json = db.Column(db.Text)
    
    timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)

    def __repr__(self):
        return f'<Verificação {self.id} [{self.tipo_verificacao}] - {self.status_geral}>'
    
    # Funções auxiliares para lidar com JSON de forma mais fácil
    def set_dados_entrada(self, dados):
        self.dados_entrada_json = json.dumps(dados)
        
    def set_resultado_completo(self, resultado):
        self.resultado_completo_json = json.dumps(resultado, indent=2)