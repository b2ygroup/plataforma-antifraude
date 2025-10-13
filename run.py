# run.py
from app import create_app, db
from app.models import Verificacao # Importa o seu modelo

app = create_app()

# NOVIDADE: Disponibiliza 'db' e 'Verificacao' automaticamente no 'flask shell'
@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Verificacao': Verificacao}

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)