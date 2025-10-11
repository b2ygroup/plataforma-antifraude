# config.py
import os

# Pega o caminho absoluto do diretório do projeto.
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'
    BRASILAPI_BASE_URL = "https://brasilapi.com.br/api/cnpj/v1/"
    
    # --- NOVA CONFIGURAÇÃO DO BANCO DE DADOS ---
    # Define o caminho para o arquivo do banco de dados SQLite.
    # Ele será criado na raiz do projeto com o nome 'antifraude.db'.
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(basedir, 'antifraude.db')
    
    # Desativa uma funcionalidade do SQLAlchemy que não usaremos e que emite avisos.
    SQLALCHEMY_TRACK_MODIFICATIONS = False