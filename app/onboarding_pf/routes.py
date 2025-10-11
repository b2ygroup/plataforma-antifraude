# app/onboarding_pf/routes.py

import time
import random
import os
import re
import json
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao
from google.cloud import vision
from google.oauth2 import service_account

bp = Blueprint('onboarding_pf', __name__)

# --- ==================================================================== ---
# --- MOTOR DE VERIFICAÇÃO V7 - OCR COMPLETO E FLUXO DE DADOS MELHORADO   ---
# --- ==================================================================== ---

def get_vision_client():
    # (Código completo da função get_vision_client, sem alterações)
    logger = current_app.logger
    google_creds_json_str = os.environ.get('GOOGLE_CREDENTIALS_JSON')
    if google_creds_json_str:
        logger.info("Autenticando no Google Vision via variável de ambiente (Produção).")
        creds_dict = json.loads(google_creds_json_str)
        credentials = service_account.Credentials.from_service_account_info(creds_dict)
        client = vision.ImageAnnotatorClient(credentials=credentials)
    else:
        logger.info("Autenticando no Google Vision via arquivo local (Desenvolvimento).")
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'
        client = vision.ImageAnnotatorClient()
    return client

def analisar_cnh_com_google_vision(doc_frente_bytes):
    """
    Função REAL de OCR, agora aprimorada para extrair a DATA DE NASCIMENTO.
    """
    logger = current_app.logger
    logger.info("OCR REAL V2: Enviando imagem para a Google Cloud Vision AI...")
    try:
        client = get_vision_client()
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            return {"status": "REPROVADO", "motivo": "Nenhum texto pôde ser lido no documento."}

        full_text = texts[0].description
        logger.debug(f"OCR REAL V2: Texto completo extraído:\n{full_text}")

        dados_extraidos = {}
        
        # Expressões regulares para extrair os dados da CNH
        # NOME (geralmente a primeira linha após "NOME")
        match_nome = re.search(r'NOME\s*\n(.+)', full_text, re.IGNORECASE)
        if match_nome: dados_extraidos['nome'] = match_nome.group(1).strip()
            
        # CPF (formato xxx.xxx.xxx-xx)
        match_cpf = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
        if match_cpf: dados_extraidos['cpf'] = match_cpf.group(1)

        # DATA DE NASCIMENTO (formato xx/xx/xxxx)
        match_nasc = re.search(r'DATA NASC\w*\s*\n(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if match_nasc: dados_extraidos['data_nascimento'] = match_nasc.group(1)

        # Nº REGISTRO
        match_registro = re.search(r'Nº\s*REGISTRO\s*\n(\d+)', full_text, re.IGNORECASE)
        if match_registro: dados_extraidos['numero_registro_cnh'] = match_registro.group(1).strip()
            
        # VALIDADE
        match_validade = re.search(r'VALIDADE\s*\n(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if match_validade: dados_extraidos['validade_cnh'] = match_validade.group(1)

        logger.info("OCR REAL V2: Dados da CNH parseados com sucesso.")
        return {
            "status": "SUCESSO",
            "tipo_documento_identificado": "CNH",
            "dados": dados_extraidos,
            "foto_3x4_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=", # Em um OCR real, esta seria a imagem da face extraída
            "texto_bruto": full_text
        }
    except Exception as e:
        logger.error(f"OCR REAL V2: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO", "motivo": "Falha na comunicação com o serviço de IA."}


# (As outras funções de simulação permanecem as mesmas)
def simular_receita_federal_pep(cpf): return { "status": "SUCESSO", "dados": { "situacao_cadastral": "REGULAR", "pep": False } }
def simular_liveness_passivo(selfie_bytes): return {"status": "APROVADO", "detalhes": "Nenhum sinal de ataque."}
def simular_liveness_ativo(): return {"status": "APROVADO", "detalhes": "Movimento detectado."}
def simular_bgc(cpf, nome): return {"status": "APROVADO", "detalhes": { "antecedentes_criminais": {"status": "NADA_CONSTA"}}}
def simular_validacao_documento_ia(doc_bytes): return {"status": "APROVADO", "score_autenticidade": 0.98}

def simular_face_match(foto_doc_base64, selfie_bytes):
    logger = current_app.logger
    logger.debug("MOCK (Face Match): Comparando biometria facial...")
    # Lógica aprimorada: se a foto do doc não foi enviada, a similaridade é baixa.
    if not foto_doc_base64 or len(foto_doc_base64) < 100:
        logger.warning("MOCK (Face Match): Foto do documento não recebida para comparação.")
        similaridade = 0.10 # Score baixo
    else:
        similaridade = random.uniform(0.90, 0.99)
    
    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
    logger.debug(f"MOCK (Face Match): Similaridade: {similaridade:.2f}, Threshold: {threshold:.2f}, Veredito: {status}")
    return {"status": status, "similaridade": similaridade, "threshold": threshold}

# O endpoint /extrair-ocr agora usa a função de OCR atualizada
@bp.route('/extrair-ocr', methods=['POST'])
def extrair_ocr():
    if 'documento_frente' not in request.files:
        return jsonify({"erro": "O arquivo 'documento_frente' é obrigatório."}), 400
    resultado_ocr = analisar_cnh_com_google_vision(request.files['documento_frente'].read())
    if resultado_ocr['status'] == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify(resultado_ocr), 400

# O endpoint /verificar agora recebe a foto do documento para o Face Match
@bp.route('/verificar', methods=['POST'])
def verificar_pessoa_fisica():
    logger = current_app.logger
    if 'documento_frente' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Arquivos 'documento_frente' e 'selfie' são obrigatórios."}), 400

    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    foto_doc_b64 = request.form.get('foto_documento_b64', '')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie = request.files['selfie']
    frente_bytes = arquivo_frente.read()
    selfie_bytes = arquivo_selfie.read()

    logger.info(f'ONBOARDING PF V5: Iniciando fluxo final com IA para {nome_cliente} (CPF: {cpf_cliente})')
    workflow_results = {}
    status_geral = "APROVADO"
    
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    workflow_results['validacao_documento_ia'] = simular_validacao_documento_ia(frente_bytes)
    
    # AGORA O FACE MATCH RECEBE A FOTO REAL EXTRAÍDA DO OCR
    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO': status_geral = "PENDENCIA"

    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)
    if workflow_results['background_check']['status'] != 'APROVADO': status_geral = "PENDENCIA"

    logger.info(f'Onboarding PF para CPF {cpf_cliente} finalizado com status GERAL: {status_geral}')
    resposta_final = { "status_geral": status_geral, "workflow_executado": workflow_results }
    
    try:
        nova_verificacao = Verificacao(tipo_verificacao='PF', status_geral=status_geral)
        nova_verificacao.set_dados_entrada({'nome': nome_cliente, 'cpf': cpf_cliente})
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200