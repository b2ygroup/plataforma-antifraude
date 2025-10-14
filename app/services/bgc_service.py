# app/services/bgc_service.py
import random
from flask import current_app

def check_background(nome: str, cpf: str = None) -> dict:
    """
    Simula uma verificação de antecedentes (BGC) para uma pessoa física.
    Agora pode operar apenas com o nome, se o CPF não for fornecido.
    """
    logger = current_app.logger
    identificador = cpf if cpf else nome
    logger.info(f"BGC Service: Iniciando verificação de antecedentes simulada para '{identificador}'...")

    # Simulação de resultados
    has_antecedentes_criminais = random.choice([True, False, False, False]) # 25% de chance de ter antecedentes
    is_pep = "SILVA" in nome.upper() # Simula que pessoas com sobrenome 'SILVA' são PEP
    has_mandado_prisao = random.random() < 0.05 # 5% de chance de ter mandado de prisão

    pendencias = []
    if has_antecedentes_criminais:
        pendencias.append("Possui antecedentes criminais em fontes públicas.")
    if is_pep:
        pendencias.append("Identificado como Pessoa Politicamente Exposta (PEP).")
    if has_mandado_prisao:
        pendencias.append("Consta um mandado de prisão em aberto.")

    if not pendencias:
        logger.info(f"BGC Service: Nenhuma pendência encontrada para '{identificador}'.")
        return {
            "status": "APROVADO",
            "detalhes": "Nenhuma pendência significativa encontrada em fontes públicas e listas restritivas."
        }
    else:
        logger.warning(f"BGC Service: Pendências encontradas para '{identificador}': {', '.join(pendencias)}")
        return {
            "status": "PENDENCIA",
            "detalhes": pendencias
        }