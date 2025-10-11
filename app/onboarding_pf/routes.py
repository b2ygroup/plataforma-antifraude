# app/onboarding_pf/routes.py

import time
import random
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao

bp = Blueprint('onboarding_pf', __name__)

# --- ==================================================================== ---
# --- MOTOR DE VERIFICAÇÃO V4 - FLUXO INTERATIVO                          ---
# --- ==================================================================== ---

def simular_receita_federal_pep(cpf):
    """Simula a consulta na Receita Federal e a verificação de Pessoa Politicamente Exposta (PEP)."""
    current_app.logger.debug(f"MOCK (Receita Federal + PEP): Consultando CPF {cpf}...")
    time.sleep(0.5)
    is_pep = random.choice([True, False])
    return {
        "status": "SUCESSO",
        "dados": {
            "situacao_cadastral": "REGULAR",
            "nome_completo_rf": "Leonardo Alves da Silva",
            "pep": is_pep
        }
    }

def simular_liveness_passivo(selfie_bytes):
    """Simula a análise de Liveness Passivo para detectar fraudes como fotos de telas, máscaras, etc."""
    current_app.logger.debug("MOCK (Liveness Passivo): Analisando características do arquivo da selfie...")
    time.sleep(1)
    score = random.uniform(0.85, 0.99)
    veredito = "APROVADO"
    motivo = "Nenhum sinal de ataque por apresentação detectado."
    current_app.logger.debug(f"MOCK (Liveness Passivo): Veredito: {veredito}")
    return {"status": veredito, "score": score, "detalhes": motivo}

def simular_liveness_ativo():
    """Simula a verificação do desafio de prova de vida (ex: sorriso)."""
    current_app.logger.debug("MOCK (Liveness Ativo): Verificando se o desafio (sorriso) foi completo...")
    time.sleep(0.5)
    veredito = "APROVADO"
    motivo = "Movimento de sorriso detectado com sucesso."
    current_app.logger.debug(f"MOCK (Liveness Ativo): Veredito: {veredito}")
    return {"status": veredito, "desafio_completado": "sorriso", "detalhes": motivo}

def simular_ocr(doc_bytes):
    """
    Simula um serviço de OCR inteligente que identifica o tipo de documento e extrai os dados.
    """
    current_app.logger.debug("MOCK (OCR): Analisando e tipificando documento...")
    time.sleep(2)
    tipo_documento = random.choice(["RG", "CNH"])
    if tipo_documento == "CNH":
        dados_extraidos = { "nome": "Leonardo A. Silva (do CNH)", "cpf": "111.222.333-44", "data_nascimento": "1995-08-10", "filiacao": "Maria da Silva", "numero_registro": "01234567890" }
    else: # RG
        dados_extraidos = { "nome": "Leonardo Alves da Silva (do RG)", "rg": "12.345.678-9", "data_expedicao": "2015-01-20", "filiacao": "Maria da Silva / Joao da Silva", "cpf_no_rg": "111.222.333-44" }
    current_app.logger.debug(f"MOCK (OCR): Documento identificado como {tipo_documento}. Dados extraídos.")
    return { "status": "SUCESSO", "tipo_documento_identificado": tipo_documento, "dados": dados_extraidos, "foto_3x4_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" }

def simular_face_match(foto_doc_base64, selfie_bytes):
    """Simula a comparação biométrica entre a foto do documento e a selfie."""
    current_app.logger.debug("MOCK (Face Match): Comparando biometria facial...")
    time.sleep(1)
    similaridade = random.uniform(0.90, 0.99)
    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
    current_app.logger.debug(f"MOCK (Face Match): Similaridade: {similaridade:.2f}, Threshold: {threshold:.2f}, Veredito: {status}")
    return {"status": status, "similaridade": similaridade, "threshold": threshold}

def simular_bgc(cpf, nome):
    """
    Simula o Background Check (BGC) com as fontes detalhadas na apresentação.
    """
    current_app.logger.debug(f"MOCK (BGC): Iniciando checagem de antecedentes para {nome}...")
    time.sleep(2)
    has_mandado_prisao = random.choice([True, False])
    detalhes = { "antecedentes_criminais": {"status": "NADA_CONSTA"}, "listas_restritivas_ofac_onu_ue_uk": {"status": "NADA_CONSTA"}, "mandados_prisao": {"status": "EM_ABERTO" if has_mandado_prisao else "NADA_CONSTA"}, "risco_telefone_email_ip": {"score_risco": random.randint(1, 100)} }
    status_final_bgc = "PENDENCIA" if has_mandado_prisao else "APROVADO"
    current_app.logger.debug(f"MOCK (BGC): Checagem finalizada com status: {status_final_bgc}")
    return {"status": status_final_bgc, "detalhes": detalhes}

def simular_validacao_documento(doc_bytes, tipo_documento):
    """Simula a validação de legitimidade do documento (Documentoscopia / Dados Biométricos)."""
    current_app.logger.debug(f"MOCK (Validação Doc): Iniciando validação de legitimidade para {tipo_documento}...")
    time.sleep(1.5)
    metodo = "Checagem via base governamental" if tipo_documento == "CNH" else "Análise por documentoscopia"
    current_app.logger.debug(f"MOCK (Validação Doc): Documento aprovado via {metodo}.")
    return {"status": "APROVADO", "metodo": metodo}

# --- ENDPOINT DE OCR REINTRODUZIDO ---
@bp.route('/extrair-ocr', methods=['POST'])
def extrair_ocr():
    logger = current_app.logger
    if 'documento' not in request.files:
        return jsonify({"erro": "O arquivo 'documento' é obrigatório."}), 400
    
    arquivo_documento = request.files['documento']
    logger.info(f'Recebido arquivo para OCR: {arquivo_documento.filename}')
    
    documento_bytes = arquivo_documento.read()
    resultado_ocr = simular_ocr(documento_bytes)
    
    if resultado_ocr['status'] == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify({"erro": "Não foi possível extrair dados do documento."}), 500

# --- ENDPOINT PRINCIPAL ATUALIZADO ---
@bp.route('/verificar', methods=['POST'])
def verificar_pessoa_fisica():
    logger = current_app.logger
    if 'documento' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Os arquivos 'documento' e 'selfie' são obrigatórios."}), 400

    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    arquivo_documento = request.files['documento']
    arquivo_selfie = request.files['selfie']
    
    logger.info(f'ONBOARDING PF V4: Iniciando fluxo final para {nome_cliente} (CPF: {cpf_cliente})')
    documento_bytes = arquivo_documento.read()
    selfie_bytes = arquivo_selfie.read()

    workflow_results = {}
    status_geral = "APROVADO"
    
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    if workflow_results['liveness_ativo']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    if workflow_results['liveness_passivo']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    foto_doc_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=" 
    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)
    if workflow_results['background_check']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    tipo_doc = request.form.get('tipo_documento', 'RG') 
    workflow_results['validacao_documento'] = simular_validacao_documento(documento_bytes, tipo_doc)
    if workflow_results['validacao_documento']['status'] != 'APROVADO': status_geral = "PENDENCIA"

    logger.info(f'Onboarding PF para CPF {cpf_cliente} finalizado com status GERAL: {status_geral}')
    resposta_final = { "status_geral": status_geral, "workflow_executado": workflow_results }
    
    try:
        nova_verificacao = Verificacao(tipo_verificacao='PF', status_geral=status_geral)
        nova_verificacao.set_dados_entrada({'nome': nome_cliente, 'cpf': cpf_cliente})
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f'Verificação do CPF {cpf_cliente} salva no BD com ID: {nova_verificacao.id}')
    except Exception as e:
        logger.error(f'Falha ao salvar verificação do CPF {cpf_cliente} no BD: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200