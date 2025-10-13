# config.py
import os
from dotenv import load_dotenv

# Pega o caminho absoluto do diretório do projeto.
basedir = os.path.abspath(os.path.dirname(__file__))

# NOVIDADE: Carrega as variáveis de ambiente do arquivo .env na pasta raiz do projeto
load_dotenv(os.path.join(basedir, '..', '.env'))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'uma-chave-secreta-muito-dificil-de-adivinhar'
    BRASILAPI_BASE_URL = "https://brasilapi.com.br/api/cnpj/v1/"
    
    # --- LÓGICA DO BANCO DE DADOS CENTRALIZADA E CORRIGIDA ---
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Pega a DATABASE_URL do ambiente
    DATABASE_URL = os.environ.get('DATABASE_URL')
    
    # Corrige o prefixo para o SQLAlchemy (importante para Heroku/Vercel)
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
    
    # Define a configuração final, com um fallback para SQLite se a DATABASE_URL não estiver definida
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or 'sqlite:///' + os.path.join(basedir, 'antifraude.db')