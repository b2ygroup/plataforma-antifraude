# app/__init__.py

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from config import Config
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # LÊ A URL DO BANCO DE DADOS DO AMBIENTE (FORNECIDA PELO VERCEL)
    # E AJUSTA PARA O DIALETO DO POSTGRESQL DO SQLAlchemy
    db_url = os.environ.get('DATABASE_URL')
    if db_url and db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url

    db.init_app(app)

    # --- REGISTRO DOS BLUEPRINTS ---
    from app.onboarding_pj.routes import bp as onboarding_pj_bp
    app.register_blueprint(onboarding_pj_bp, url_prefix='/onboarding/pj')
    from app.onboarding_pf.routes import bp as onboarding_pf_bp
    app.register_blueprint(onboarding_pf_bp, url_prefix='/onboarding/pf')
    from app.autenticacao.routes import bp as autenticacao_bp
    app.register_blueprint(autenticacao_bp, url_prefix='/autenticacao')

    @app.route('/')
    def index():
        return render_template('index.html')

    # --- ROTA TEMPORÁRIA PARA CRIAR O BANCO DE DADOS ---
    # DEPOIS DE USAR UMA VEZ, PODEMOS REMOVÊ-LA POR SEGURANÇA
    @app.route('/init-db-super-secret')
    def init_db():
        with app.app_context():
            db.create_all()
        return "Banco de dados inicializado com sucesso!"

    # --- CONFIGURAÇÃO DO SISTEMA DE LOGS ---
    # No Vercel, os logs são gerenciados automaticamente, então não precisamos de logs em arquivo.
    
    return app