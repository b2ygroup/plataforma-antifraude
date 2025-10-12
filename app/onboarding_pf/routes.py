# app/onboarding/pf/routes.py

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

# Configuração do Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
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
    logger.info("OCR REAL V4: Iniciando análise com Google Vision AI...")
    try:
        client = get_vision_client()
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        if not texts:
            return {"status": "REPROVADO_OCR", "motivo": "Não conseguimos ler os dados do documento."}

        full_text = texts[0].description
        dados_extraidos = {}

        # Expressões regulares aprimoradas
        match_nome = re.search(r'NOME\s*\n(.+)', full_text, re.IGNORECASE)
        if match_nome:
            dados_extraidos['nome'] = match_nome.group(1).strip()

        match_cpf = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
        if match_cpf:
            dados_extraidos['cpf'] = match_cpf.group(1)

        # Regex aprimorada para data de nascimento, procurando em mais contextos
        match_nasc = re.search(r'NASCIMENTO\s*\n?(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if match_nasc:
            dados_extraidos['data_nascimento'] = match_nasc.group(1)

        if 'nome' not in dados_extraidos or 'cpf' not in dados_extraidos:
            return {"status": "REPROVADO_OCR", "motivo": "Não foi possível extrair nome e CPF."}

        logger.info("OCR REAL V4: Dados da CNH parseados com sucesso.")
        return {
            "status": "SUCESSO",
            "tipo_documento_identificado": "CNH",
            "dados": dados_extraidos,
            "foto_3x4_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        }
    except Exception as e:
        logger.error(f"OCR REAL V4: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO_API", "motivo": "Falha na comunicação com o serviço de IA."}


def simular_liveness_ativo():
    return {"status": "APROVADO", "detalhes": "Desafios de prova de vida (IA) completados com sucesso."}


def simular_receita_federal_pep(cpf):
    return {"status": "SUCESSO", "dados": {"situacao_cadastral": "REGULAR", "pep": False}}


def simular_liveness_passivo(selfie_bytes):
    return {"status": "APROVADO", "detalhes": "Nenhum sinal de ataque."}


def simular_face_match(foto_doc_base64, selfie_bytes):
    return {"status": "APROVADO", "similaridade": random.uniform(0.90, 0.99)}


def simular_bgc(cpf, nome):
    return {"status": "PENDENCIA", "detalhes": {"mandados_prisao": {"status": "EM_ABERTO"}}}


def simular_validacao_documento_ia(doc_bytes):
    return {"status": "PENDENCIA", "score_autenticidade": 0.85}


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

    logger.info(f'ONBOARDING V8: Iniciando fluxo final com IA para {nome_cliente}')

    try:
        upload_result_doc = cloudinary.uploader.upload(arquivo_frente, folder="onboarding_docs")
        doc_frente_url = upload_result_doc.get('secure_url')
        upload_result_selfie = cloudinary.uploader.upload(arquivo_selfie, folder="onboarding_selfies")
        selfie_url = upload_result_selfie.get('secure_url')
    except Exception as e:
        logger.error(f"Erro no upload para o Cloudinary: {e}")
        return jsonify({"erro": "Falha ao salvar as imagens de evidência."}), 500

    arquivo_frente.seek(0)
    frente_bytes = arquivo_frente.read()
    arquivo_selfie.seek(0)
    selfie_bytes = arquivo_selfie.read()

    workflow_results = {}
    status_geral = "APROVADO"

    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    
    workflow_results['validacao_documento_ia'] = simular_validacao_documento_ia(frente_bytes)
    if workflow_results['validacao_documento_ia']['status'] != 'APROVADO':
        status_geral = "PENDENCIA"

    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO':
        status_geral = "PENDENCIA"

    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)
    if workflow_results['background_check']['status'] != 'APROVADO':
        status_geral = "PENDENCIA"

    resposta_final = {"status_geral": status_geral, "workflow_executado": workflow_results}

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
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200