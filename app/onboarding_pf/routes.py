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
import cloudinary
import cloudinary.uploader

bp = Blueprint('onboarding_pf', __name__)

# --- CONFIGURAÇÃO DO CLOUDINARY ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

def get_vision_client():
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
    logger = current_app.logger
    logger.info("OCR REAL V3: Iniciando análise com Google Vision AI...")
    if len(doc_frente_bytes) < 100 * 1024:
        logger.warning(f"OCR REAL V3: Imagem com baixa qualidade detectada (tamanho: {len(doc_frente_bytes)} bytes).")
        return {"status": "REPROVADO_QUALIDADE", "motivo": "A foto do documento parece estar em baixa resolução ou sem foco."}
    try:
        client = get_vision_client()
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        if not texts:
            return {"status": "REPROVADO_OCR", "motivo": "Não conseguimos ler os dados do documento."}
        full_text = texts[0].description
        dados_extraidos = {}
        match_nome = re.search(r'NOME\s*\n(.+)', full_text, re.IGNORECASE)
        if match_nome: dados_extraidos['nome'] = match_nome.group(1).strip()
        match_cpf = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
        if match_cpf: dados_extraidos['cpf'] = match_cpf.group(1)
        match_nasc = re.search(r'DATA NASC\w*\s*\n(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if match_nasc: dados_extraidos['data_nascimento'] = match_nasc.group(1)
        if 'nome' not in dados_extraidos or 'cpf' not in dados_extraidos:
             return {"status": "REPROVADO_OCR", "motivo": "Não foi possível extrair os campos essenciais."}
        logger.info("OCR REAL V3: Dados da CNH parseados com sucesso.")
        return {"status": "SUCESSO", "tipo_documento_identificado": "CNH", "dados": dados_extraidos, "foto_3x4_base64": "...", "texto_bruto": full_text}
    except Exception as e:
        logger.error(f"OCR REAL V3: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO_API", "motivo": "Falha na comunicação com o serviço de IA."}

def simular_receita_federal_pep(cpf):
    return { "status": "SUCESSO", "dados": { "situacao_cadastral": "REGULAR", "pep": False } }
def simular_liveness_passivo(selfie_bytes):
    return {"status": "APROVADO", "detalhes": "Nenhum sinal de ataque."}
def simular_liveness_ativo():
    return {"status": "APROVADO", "detalhes": "Movimento detectado."}
def simular_face_match(foto_doc_base64, selfie_bytes):
    return {"status": "APROVADO", "similaridade": 0.95}
def simular_bgc(cpf, nome):
    return {"status": "APROVADO", "detalhes": { "antecedentes_criminais": {"status": "NADA_CONSTA"}}}
def simular_validacao_documento_ia(doc_frente_bytes, doc_verso_bytes):
    return {"status": "APROVADO", "score_autenticidade": 0.98}

@bp.route('/extrair-ocr', methods=['POST'])
def extrair_ocr():
    if 'documento_frente' not in request.files:
        return jsonify({"erro": "O arquivo 'documento_frente' é obrigatório."}), 400
    resultado_ocr = analisar_cnh_com_google_vision(request.files['documento_frente'].read())
    if resultado_ocr.get('status') == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify(resultado_ocr), 400

@bp.route('/verificar', methods=['POST'])
def verificar_pessoa_fisica():
    logger = current_app.logger
    if 'documento_frente' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Arquivos 'documento_frente' e 'selfie' são obrigatórios."}), 500

    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    foto_doc_b64 = request.form.get('foto_documento_b64', '')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie = request.files['selfie']
    
    logger.info(f'ONBOARDING V6: Iniciando fluxo com upload de imagens para {nome_cliente}')

    try:
        logger.debug("Fazendo upload da imagem do documento para o Cloudinary...")
        upload_result_doc = cloudinary.uploader.upload(arquivo_frente, folder="onboarding_docs")
        doc_frente_url = upload_result_doc.get('secure_url')
        logger.info(f"Upload do documento concluído. URL: {doc_frente_url}")

        logger.debug("Fazendo upload da imagem da selfie para o Cloudinary...")
        upload_result_selfie = cloudinary.uploader.upload(arquivo_selfie, folder="onboarding_selfies")
        selfie_url = upload_result_selfie.get('secure_url')
        logger.info(f"Upload da selfie concluído. URL: {selfie_url}")

    except Exception as e:
        logger.error(f"Erro no upload para o Cloudinary: {e}")
        return jsonify({"erro": "Falha ao salvar as imagens de evidência."}), 500

    selfie_bytes = arquivo_selfie.read()
    frente_bytes = arquivo_frente.read() # Ler novamente, pois o upload consome o stream
    arquivo_frente.seek(0)
    selfie_bytes = arquivo_selfie.read()
    arquivo_selfie.seek(0)

    workflow_results = {}
    status_geral = "APROVADO"
    
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    workflow_results['validacao_documento_ia'] = simular_validacao_documento_ia(frente_bytes, b'')
    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)

    for key, result in workflow_results.items():
        if result.get('status') != 'APROVADO' and result.get('status') != 'SUCESSO':
            status_geral = 'PENDENCIA'
            break
            
    resposta_final = { "status_geral": status_geral, "workflow_executado": workflow_results }
    
    try:
        nova_verificacao = Verificacao(
            tipo_verificacao='PF',
            status_geral=status_geral,
            doc_frente_url=doc_frente_url,
            selfie_url=selfie_url
        )
        nova_verificacao.set_dados_entrada({'nome': nome_cliente, 'cpf': cpf_cliente})
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f'Verificação e URLs das imagens salvas no BD com ID: {nova_verificacao.id}')
    except Exception as e:
        logger.error(f'Falha ao salvar verificação no BD: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200