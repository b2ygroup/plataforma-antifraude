# run.py
from app import create_app, db
from app.models import Verificacao
import click

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Verificacao': Verificacao}

@app.cli.command("create-db")
def create_db_command():
    """Cria as tabelas da base de dados."""
    with app.app_context():
        db.create_all()
    click.echo("Base de dados criada com sucesso.")

@app.cli.command("clear-db")
def clear_db_command():
    """Limpa e recria as tabelas da base de dados."""
    with app.app_context():
        db.drop_all()
        db.create_all()
    click.echo("Base de dados limpa e recriada com sucesso.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)