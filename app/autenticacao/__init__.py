# app/autenticacao/__init__.py

from flask import Blueprint

# Cria o Blueprint aqui, no arquivo principal do módulo
bp = Blueprint('autenticacao', __name__)

# Importa as rotas no final para evitar dependências circulares
from app.autenticacao import routes