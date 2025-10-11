# app/onboarding_pj/routes.py

import requests
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao

# Criação do Blueprint para este módulo.
bp = Blueprint('onboarding_pj', __name__)


# --- Funções Mock (Simuladas) ---
def consultar_tribunais_mock(cnpj):
    """Função simulada para consultar processos em tribunais."""
    # Lógica de simulação: um em cada cinco CNJPs terá pendência.
    if int(cnpj[-2]) % 5 == 0:
        return {"status": "PENDENCIA", "detalhes": "Encontrado 1 processo no Tribunal de Justiça."}
    return {"status": "APROVADO", "detalhes": "Nenhum processo encontrado."}

def consultar_listas_internacionais_mock(nome_empresa):
    """Função simulada para consultar listas internacionais (OFAC, ONU, etc.)."""
    if "block" in nome_empresa.lower(): # Simula uma empresa bloqueada
        return {"status": "PENDENCIA", "detalhes": "Nome consta na lista da OFAC."}
    return {"status": "APROVADO", "detalhes": "Nome não consta em listas restritivas."}


@bp.route('/verificar', methods=['POST'])
def verificar_empresa():
    # Pega a instância do logger configurada no __init__.py
    logger = current_app.logger
    
    dados = request.get_json()
    if not dados or 'cnpj' not in dados:
        logger.warning('Requisição de verificação de PJ recebida sem CNPJ.')
        return jsonify({"erro": "O campo 'cnpj' é obrigatório."}), 400

    cnpj = dados['cnpj'].replace(".", "").replace("/", "").replace("-", "")
    logger.info(f'Iniciando verificação para o CNPJ: {cnpj}')
    
    resultados_finais = {
        "verificacoes": []
    }
    status_geral = "APROVADO"
    nome_empresa = ""

    # --- Etapa 1: Consulta à Receita Federal ---
    try:
        url_receita = f"{current_app.config['BRASILAPI_BASE_URL']}{cnpj}"
        response_receita = requests.get(url_receita)
        response_receita.raise_for_status()
        dados_receita = response_receita.json()
        resultados_finais["verificacoes"].append({
            "fonte": "Receita Federal",
            "status": "APROVADO",
            "dados": dados_receita
        })
        nome_empresa = dados_receita.get("razao_social", "")
        logger.info(f'CNPJ {cnpj} encontrado na Receita Federal. Razão Social: {nome_empresa}')
    except requests.exceptions.HTTPError as e:
        status_geral = "PENDENCIA"
        resultados_finais["verificacoes"].append({
            "fonte": "Receita Federal",
            "status": "PENDENCIA",
            "erro": f"CNPJ não encontrado ou inválido. Detalhes: {str(e)}"
        })
        logger.error(f'Erro ao consultar CNPJ {cnpj} na Receita: {e}')
        # Mesmo com erro, salvamos o registro da tentativa
    except Exception as e:
        logger.error(f'Erro inesperado ao consultar CNPJ {cnpj} na Receita: {e}')
        return jsonify({"erro": f"Erro interno ao consultar Receita Federal: {str(e)}"}), 500

    # Etapa 2: Consulta aos Tribunais
    resultado_tribunais = consultar_tribunais_mock(cnpj)
    if resultado_tribunais["status"] == "PENDENCIA":
        status_geral = "PENDENCIA"
    resultados_finais["verificacoes"].append({
        "fonte": "Tribunais de Justiça",
        "status": resultado_tribunais["status"],
        "detalhes": resultado_tribunais["detalhes"]
    })
    logger.debug(f'Resultado da verificação de Tribunais para {cnpj}: {resultado_tribunais["status"]}')

    # Etapa 3: Consulta às Listas Internacionais
    if nome_empresa:
        resultado_listas = consultar_listas_internacionais_mock(nome_empresa)
        if resultado_listas["status"] == "PENDENCIA":
            status_geral = "PENDENCIA"
        resultados_finais["verificacoes"].append({
            "fonte": "Listas Internacionais",
            "status": resultado_listas["status"],
            "detalhes": resultado_listas["detalhes"]
        })
        logger.debug(f'Resultado da verificação de Listas para {nome_empresa}: {resultado_listas["status"]}')

    resultados_finais["status_geral"] = status_geral
    logger.info(f'Verificação para o CNPJ {cnpj} finalizada com status: {status_geral}')

    # --- AUTOMATIZAÇÃO: Salvando no Banco de Dados ---
    try:
        nova_verificacao = Verificacao(
            tipo_verificacao='PJ',
            status_geral=status_geral
        )
        nova_verificacao.set_dados_entrada({'cnpj': cnpj})
        nova_verificacao.set_resultado_completo(resultados_finais)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f'Verificação do CNPJ {cnpj} salva no banco de dados com ID: {nova_verificacao.id}')
    except Exception as e:
        logger.error(f'Falha ao salvar verificação do CNPJ {cnpj} no banco de dados: {e}')
        db.session.rollback()

    return jsonify(resultados_finais), 200