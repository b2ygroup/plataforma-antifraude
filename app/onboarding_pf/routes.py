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

# --- CONFIGURAÇÃO DO CLOUDINARY ---
cloudinary.config(
    cloud_name = os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key = os.environ.get('CLOUDINARY_API_KEY'),
    api_secret = os.environ.get('CLOUDINARY_API_SECRET'),
    secure = True
)

def get_vision_client():
    """
    Cria e retorna um cliente da Google Vision AI, priorizando credenciais de ambiente.
    """
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
    Função REAL que envia a imagem de um documento para a Google Vision AI e interpreta os dados.
    """
    logger = current_app.logger
    logger.info("OCR REAL: Iniciando análise com Google Vision AI...")
    
    try:
        client = get_vision_client()
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            logger.warning("OCR REAL: Nenhum texto detectado pela IA.")
            return {"status": "REPROVADO_OCR", "motivo": "Não conseguimos ler os dados do documento. Tente novamente com melhor iluminação e sem reflexos."}

        full_text = texts[0].description
        logger.debug(f"OCR REAL: Texto completo extraído:\n{full_text}")

        dados_extraidos = {}
        
        match_nome = re.search(r'NOME\s*\n(.+)', full_text, re.IGNORECASE)
        if match_nome: dados_extraidos['nome'] = match_nome.group(1).strip()
            
        match_cpf = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
        if match_cpf: dados_extraidos['cpf'] = match_cpf.group(1)

        match_nasc = re.search(r'DATA NASC\w*\s*\n(\d{2}/\d{2}/\d{4})', full_text, re.IGNORECASE)
        if match_nasc: dados_extraidos['data_nascimento'] = match_nasc.group(1)

        if 'nome' not in dados_extraidos or 'cpf' not in dados_extraidos:
             return {"status": "REPROVADO_OCR", "motivo": "Não foi possível extrair os campos essenciais. Por favor, tire outra foto com o documento bem enquadrado."}

        logger.info("OCR REAL: Dados da CNH parseados com sucesso.")
        return {
            "status": "SUCESSO",
            "tipo_documento_identificado": "CNH",
            "dados": dados_extraidos,
            "foto_3x4_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=",
            "texto_bruto": full_text
        }
        
    except Exception as e:
        logger.error(f"OCR REAL: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO_API", "motivo": "Falha na comunicação com o serviço de IA."}

def simular_receita_federal_pep(cpf):
    """Simula a consulta na Receita Federal e a verificação de Pessoa Politicamente Exposta (PEP)."""
    current_app.logger.debug(f"MOCK (Receita Federal + PEP): Consultando CPF {cpf}...")
    time.sleep(0.5)
    is_pep = random.choice([True, False])
    return { "status": "SUCESSO", "dados": { "situacao_cadastral": "REGULAR", "nome_completo_rf": "Leonardo Alves da Silva", "pep": is_pep } }

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
    current_app.logger.debug("MOCK (Liveness Ativo): Verificando se os desafios (piscar, sorrir) foram completos...")
    time.sleep(0.5)
    veredito = "APROVADO"
    motivo = "Desafios de prova de vida completados com sucesso."
    current_app.logger.debug(f"MOCK (Liveness Ativo): Veredito: {veredito}")
    return {"status": veredito, "desafio_completado": "piscar_e_sorrir", "detalhes": motivo}

def simular_face_match(foto_doc_base64, selfie_bytes):
    """Simula a comparação biométrica entre a foto do documento e a selfie."""
    logger = current_app.logger
    logger.debug("MOCK (Face Match): Comparando biometria facial...")
    if not foto_doc_base64 or len(foto_doc_base64) < 100:
        logger.warning("MOCK (Face Match): Foto do documento não recebida para comparação.")
        similaridade = 0.10
    else:
        similaridade = random.uniform(0.90, 0.99)
    threshold = current_app.config.get('FACE_MATCH_THRESHOLD', 0.90)
    status = "APROVADO" if similaridade >= threshold else "PENDENCIA"
    logger.debug(f"MOCK (Face Match): Similaridade: {similaridade:.2f}, Threshold: {threshold:.2f}, Veredito: {status}")
    return {"status": status, "similaridade": similaridade, "threshold": threshold}

def simular_bgc(cpf, nome):
    """Simula o Background Check (BGC) com as fontes detalhadas na apresentação."""
    current_app.logger.debug(f"MOCK (BGC): Iniciando checagem de antecedentes para {nome}...")
    time.sleep(2)
    has_mandado_prisao = random.choice([True, False])
    detalhes = { "antecedentes_criminais": {"status": "NADA_CONSTA"}, "listas_restritivas_ofac_onu_ue_uk": {"status": "NADA_CONSTA"}, "mandados_prisao": {"status": "EM_ABERTO" if has_mandado_prisao else "NADA_CONSTA"}, "risco_telefone_email_ip": {"score_risco": random.randint(1, 100)} }
    status_final_bgc = "PENDENCIA" if has_mandado_prisao else "APROVADO"
    current_app.logger.debug(f"MOCK (BGC): Checagem finalizada com status: {status_final_bgc}")
    return {"status": status_final_bgc, "detalhes": detalhes}

def simular_validacao_documento_ia(doc_bytes):
    """Simula uma análise de IA (Documentoscopia) para verificar a autenticidade do documento."""
    current_app.logger.debug("MOCK (Documentoscopia IA): Analisando padrões de segurança, hologramas e microtextos...")
    time.sleep(2)
    score_autenticidade = random.uniform(0.80, 0.99)
    if score_autenticidade < 0.92:
        veredito = "PENDENCIA"
        motivo = "Inconsistências detectadas nos padrões de segurança do documento."
    else:
        veredito = "APROVADO"
        motivo = "Padrões de segurança do documento validados com sucesso."
    current_app.logger.debug(f"MOCK (Documentoscopia IA): Veredito: {veredito} (Score: {score_autenticidade:.2f})")
    return {"status": veredito, "score_autenticidade": score_autenticidade, "detalhes": motivo}

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
    
    logger.info(f'ONBOARDING V7: Iniciando fluxo final com IA para {nome_cliente}')

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
    if workflow_results['validacao_documento_ia']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['face_match'] = simular_face_match(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)
    if workflow_results['background_check']['status'] != 'APROVADO': status_geral = "PENDENCIA"

    logger.info(f'Onboarding PF para CPF {cpf_cliente} finalizado com status GERAL: {status_geral}')
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
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200