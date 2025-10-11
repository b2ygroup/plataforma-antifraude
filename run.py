# run.py

# --- Documentação do Módulo ---
# Este é o ponto de entrada principal para executar a aplicação.
# Ele importa a função fábrica 'create_app' do nosso pacote 'app'
# e inicia o servidor de desenvolvimento do Flask.

from app import create_app

# Cria a instância da nossa aplicação chamando a função fábrica.
app = create_app()

# Este bloco condicional garante que o servidor só será executado
# quando este script for chamado diretamente pelo interpretador Python.
if __name__ == '__main__':
    # app.run() inicia o servidor.
    # host='0.0.0.0' faz o servidor ser acessível por outros dispositivos na mesma rede.
    # port=5000 define a porta.
    # debug=True ativa o modo de depuração, que reinicia o servidor a cada alteração no código.
    app.run(host='0.0.0.0', port=5000, debug=True)