# app/onboarding_pf/routes.py

import time
import random
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao

bp = Blueprint('onboarding_pf', __name__)

# --- ==================================================================== ---
# --- MOTOR DE VERIFICAÇÃO V3 - ADICIONANDO LIVENESS ATIVO                ---
# --- ==================================================================== ---

# (As funções simular_receita_federal_pep, simular_liveness_passivo, simular_ocr, 
# simular_face_match, simular_bgc, e simular_validacao_documento continuam exatamente as mesmas)
def simular_receita_federal_pep(cpf):
    current_app.logger.debug(f"MOCK (Receita Federal + PEP): Consultando CPF {cpf}...")
    time.sleep(0.5)
    is_pep = random.choice([True, False])
    return { "status": "SUCESSO", "dados": { "situacao_cadastral": "REGULAR", "nome_completo_rf": "Leonardo Alves da Silva", "pep": is_pep } }

def simular_liveness_passivo(selfie_bytes):
    current_app.logger.debug("MOCK (Liveness Passivo): Analisando características do arquivo da selfie...")
    time.sleep(1)
    score = random.uniform(0.85, 0.99)
    veredito = "APROVADO"
    motivo = "Nenhum sinal de ataque por apresentação detectado."
    current_app.logger.debug(f"MOCK (Liveness Passivo): Veredito: {veredito}")
    return {"status": veredito, "score": score, "detalhes": motivo}

# >>> NOVA FUNÇÃO <<<
def simular_liveness_ativo():
    """Simula a verificação do desafio de prova de vida (ex: sorriso)."""
    current_app.logger.debug("MOCK (Liveness Ativo): Verificando se o desafio (sorriso) foi completo...")
    time.sleep(0.5)
    # Aqui, um sistema real analisaria o vídeo/fotos para confirmar o movimento.
    # Nossa simulação sempre aprovará.
    veredito = "APROVADO"
    motivo = "Movimento de sorriso detectado com sucesso."
    current_app.logger.debug(f"MOCK (Liveness Ativo): Veredito: {veredito}")
    return {"status": veredito, "desafio_completado": "sorriso", "detalhes": motivo}

def simular_ocr(doc_bytes):
    current_app.logger.debug("MOCK (OCR): Analisando e tipificando documento...")
    time.sleep(2)
    tipo_documento = random.choice(["RG", "CNH"])
    if tipo_documento == "CNH":
        dados_extraidos = { "nome": "Leonardo A. Silva", "cpf": "111.222.333-44", "data_nascimento": "1995-08-10", "filiacao": "Maria da Silva", "numero_registro": "01234567890" }
    else:
        dados_extraidos = { "nome": "Leonardo Alves da Silva", "rg": "12.345.678-9", "data_expedicao": "2015-01-20", "filiacao": "Maria da Silva / Joao da Silva", "cpf_no_rg": "111.222.333-44" }
    current_app.logger.debug(f"MOCK (OCR): Documento identificado como {tipo_documento}. Dados extraídos.")
    return { "status": "SUCESSO", "tipo_documento_identificado": tipo_documento, "dados": dados_extraidos, "foto_3x4_base64": "..." }

def simular_face_match(foto_doc_base64, selfie_bytes):
    current_app.logger.debug("MOCK (Face Match): Comparando biometria facial...")
    time.sleep(1)
    similaridade = random.uniform(0.90, 0.99)
    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
    current_app.logger.debug(f"MOCK (Face Match): Similaridade: {similaridade:.2f}, Threshold: {threshold:.2f}, Veredito: {status}")
    return {"status": status, "similaridade": similaridade, "threshold": threshold}

def simular_bgc(cpf, nome):
    current_app.logger.debug(f"MOCK (BGC): Iniciando checagem de antecedentes para {nome}...")
    time.sleep(2)
    has_mandado_prisao = random.choice([True, False])
    detalhes = { "antecedentes_criminais": {"status": "NADA_CONSTA"}, "listas_restritivas_ofac_onu_ue_uk": {"status": "NADA_CONSTA"}, "mandados_prisao": {"status": "EM_ABERTO" if has_mandado_prisao else "NADA_CONSTA"}, "risco_telefone_email_ip": {"score_risco": random.randint(1, 100)} }
    status_final_bgc = "PENDENCIA" if has_mandado_prisao else "APROVADO"
    current_app.logger.debug(f"MOCK (BGC): Checagem finalizada com status: {status_final_bgc}")
    return {"status": status_final_bgc, "detalhes": detalhes}

def simular_validacao_documento(doc_bytes, tipo_documento):
    current_app.logger.debug(f"MOCK (Validação Doc): Iniciando validação de legitimidade para {tipo_documento}...")
    time.sleep(1.5)
    metodo = "Checagem via base governamental" if tipo_documento == "CNH" else "Análise por documentoscopia"
    current_app.logger.debug(f"MOCK (Validação Doc): Documento aprovado via {metodo}.")
    return {"status": "APROVADO", "metodo": metodo}

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
    logger.info(f'ONBOARDING PF V3: Iniciando fluxo para {nome_cliente} (CPF: {cpf_cliente})')
    documento_bytes = arquivo_documento.read()
    selfie_bytes = arquivo_selfie.read()

    workflow_results = {}
    status_geral = "APROVADO"

    # --- Executando o fluxo com Liveness Ativo e Passivo ---
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    
    # Adicionamos a verificação de Liveness Ativo
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    if workflow_results['liveness_ativo']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    if workflow_results['liveness_passivo']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['ocr'] = simular_ocr(documento_bytes)
    if workflow_results['ocr']['status'] != 'SUCESSO': status_geral = "PENDENCIA"
    
    foto_doc_b64 = workflow_results['ocr'].get("foto_3x4_base64", "")
    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    cpf_para_bgc = workflow_results['ocr'].get("dados", {}).get("cpf", cpf_cliente)
    nome_para_bgc = workflow_results['ocr'].get("dados", {}).get("nome", nome_cliente)
    workflow_results['background_check'] = simular_bgc(cpf_para_bgc, nome_para_bgc)
    if workflow_results['background_check']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    tipo_doc = workflow_results['ocr'].get("tipo_documento_identificado", "DESCONHECIDO")
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