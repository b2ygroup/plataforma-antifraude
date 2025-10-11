# app/__init__.py

import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template  # Importe o render_template
from config import Config
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # --- REGISTRO DOS BLUEPRINTS ---
    from app.onboarding_pj.routes import bp as onboarding_pj_bp
    app.register_blueprint(onboarding_pj_bp, url_prefix='/onboarding/pj')
    from app.onboarding_pf.routes import bp as onboarding_pf_bp
    app.register_blueprint(onboarding_pf_bp, url_prefix='/onboarding/pf')
    from app.autenticacao.routes import bp as autenticacao_bp
    app.register_blueprint(autenticacao_bp, url_prefix='/autenticacao')

    # --- NOVA ROTA PARA A PÁGINA INICIAL ---
    @app.route('/')
    def index():
        """
        Esta função será executada quando alguém acessar a raiz do site.
        Ela renderiza e retorna o arquivo index.html da pasta de templates.
        """
        return render_template('index.html')

    # --- CONFIGURAÇÃO DO SISTEMA DE LOGS ---
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/plataforma.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('Plataforma Anti-Fraude iniciada')

    return app