# app/__init__.py

import os
from flask import Flask, render_template
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
    from app.autenticacao import bp as autenticacao_bp
    app.register_blueprint(autenticacao_bp, url_prefix='/autenticacao')
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/pj')
    def onboarding_pj_page():
        return render_template('onboarding_pj.html')
        
    # NOVIDADE: Rota para a nova página de Autenticação
    @app.route('/autenticar-usuario')
    def autenticacao_page():
        return render_template('autenticacao.html')

    @app.route('/init-db-super-secret')
    def init_db():
        with app.app_context():
            db.create_all()
        return "Banco de dados inicializado com sucesso!"

    @app.route('/clear-db-super-secret')
    def clear_db():
        with app.app_context():
            db.drop_all()
            db.create_all()
        return "Banco de dados limpo e recriado com sucesso!"
    
    return app