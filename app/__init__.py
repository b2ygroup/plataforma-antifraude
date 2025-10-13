# app/__init__.py

from flask import Flask, render_template
from config import Config
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # --- REGISTRO DOS BLUEPRINTS (DENTRO DA FUNÇÃO) ---
    # Esta é a correção principal. Ao importar aqui, evitamos dependências circulares.
    from app.onboarding_pj.routes import bp as onboarding_pj_bp
    app.register_blueprint(onboarding_pj_bp, url_prefix='/onboarding/pj')
    
    from app.onboarding_pf.routes import bp as onboarding_pf_bp
    app.register_blueprint(onboarding_pf_bp, url_prefix='/onboarding/pf')
    
    from app.autenticacao.routes import bp as autenticacao_bp
    app.register_blueprint(autenticacao_bp, url_prefix='/autenticacao')
    
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

    # --- ROTAS PRINCIPAIS DA APLICAÇÃO ---
    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/pj')
    def onboarding_pj_page():
        return render_template('onboarding_pj.html')

    @app.route('/autenticar-usuario')
    def autenticacao_page():
        return render_template('autenticacao.html')
    
    return app