# app/onboarding/pf/routes.py
import os
import re
import json
from functools import wraps
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao
from google.cloud import vision
from google.oauth2 import service_account
import cloudinary
import cloudinary.uploader
from app.services import bgc_service, biometrics_service, data_service, document_service, score_service

bp = Blueprint('onboarding_pJ', __name__)

cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME'),
    api_key=os.environ.get('CLOUDINARY_API_KEY'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET'),
    secure=True
)

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = os.environ.get('PLATFORM_API_KEY')
        if not api_key:
            current_app.logger.error("A autenticação de API não está configurada no servidor (PLATFORM_API_KEY não encontrada).")
            return jsonify({"erro": "A autenticação de API não está configurada no servidor."}), 500
        
        if request.headers.get('X-API-KEY') and request.headers.get('X-API-KEY') == api_key:
            return f(*args, **kwargs)
        else:
            current_app.logger.warning("Tentativa de acesso não autorizado: Chave de API inválida ou não fornecida.")
            return jsonify({"erro": "Chave de API inválida ou não fornecida."}), 401
    return decorated_function

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
        credentials_path = os.path.join(current_app.root_path, '..', 'google-credentials.json')
        if os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            client = vision.ImageAnnotatorClient()
        else:
            logger.error("Arquivo de credenciais do Google (google-credentials.json) não encontrado para desenvolvimento local.")
            client = None
    return client

def analisar_documento_com_google_vision(doc_frente_bytes):
    logger = current_app.logger
    logger.info("OCR V7: Iniciando análise de documento...")
    try:
        client = get_vision_client()
        if client is None:
            return {"status": "ERRO_CONFIGURACAO", "motivo": "Serviço de OCR não configurado corretamente."}

        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        if not texts:
            return {"status": "REPROVADO_OCR", "motivo": "Não foi possível detetar texto no documento."}

        full_text_com_newlines = texts[0].description
        logger.info(f"OCR V7: Texto completo extraído:\n---\n{full_text_com_newlines}\n---")
        
        full_text_flat = full_text_com_newlines.replace('\n', ' ')
        dados_extraidos = {}
        campos_faltando = []

        cpf_padroes = [r'(\d{3}\.\d{3}\.\d{3}-\d{2})', r'(\d{3} \d{3} \d{3} \d{2})']
        for padrao in cpf_padroes:
            if match := re.search(padrao, full_text_flat):
                dados_extraidos['cpf'] = match.group(1)
                break
        
        nasc_padroes = [
            r'(?:DATA DE NASC|NASCIMENTO)\s*[:\s]*(\d{2}/\d{2}/\d{4})',
            r'\b(\d{2}/\d{2}/(?:19|20)\d{2})\b'
        ]
        for padrao in nasc_padroes:
            if match := re.search(padrao, full_text_flat, re.IGNORECASE):
                dados_extraidos['data_nascimento'] = match.group(1)
                break

        nome_padroes = [
            r'(?:NOME|NOME COMPLETO)\n*([A-Z\s]+?)(?=\s\s|NASCIMENTO|FILIAÇÃO|CPF|DOC|REGISTRO|$)',
            r'NOME\s*([A-Z\s]+?)(?=\s\s|NASCIMENTO|FILIAÇÃO|CPF|DOC|REGISTRO|$)',
        ]
        if 'nome' not in dados_extraidos:
             for padrao in nome_padroes:
                if match := re.search(padrao, full_text_com_newlines, re.IGNORECASE):
                    nome = match.group(1).replace('\n', ' ').strip()
                    nome = re.sub(r'\bHABILITA\b', '', nome, flags=re.IGNORECASE).strip()
                    dados_extraidos['nome'] = re.sub(r'\s+', ' ', nome)
                    break

        if 'nome' not in dados_extraidos: campos_faltando.append('nome')
        if 'cpf' not in dados_extraidos: campos_faltando.append('cpf')
        if 'data_nascimento' not in dados_extraidos: campos_faltando.append('data_nascimento')

        if campos_faltando:
            motivo = f"Não foi possível extrair os seguintes campos: {', '.join(campos_faltando)}."
            return {"status": "REPROVADO_OCR", "motivo": motivo}

        logger.info(f"OCR V7: Dados extraídos com sucesso: {dados_extraidos}")
        return {"status": "SUCESSO", "dados": dados_extraidos, "foto_3x4_base64": "..."}
    except Exception as e:
        logger.error(f"OCR V7: Erro inesperado na função de análise: {e}", exc_info=True)
        return {"status": "ERRO_API", "motivo": "Ocorreu um erro interno no serviço de IA."}


@bp.route('/extrair-ocr', methods=['POST'])
@require_api_key
def extrair_ocr():
    if 'documento_frente' not in request.files:
        return jsonify({"erro": "O arquivo 'documento_frente' é obrigatório."}), 400
    doc_bytes = request.files['documento_frente'].read()
    if not doc_bytes:
        return jsonify({"status": "REPROVADO_OCR", "motivo": "O arquivo do documento está vazio."}), 400
    resultado_ocr = analisar_documento_com_google_vision(doc_bytes)
    if resultado_ocr.get('status') == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify(resultado_ocr), 400

@bp.route('/verificar', methods=['POST'])
@require_api_key
def verificar_pessoa_fisica():
    logger = current_app.logger
    if 'documento_frente' not in request.files or 'selfie_documento' not in request.files or 'selfie_liveness' not in request.files:
        return jsonify({"erro": "Todos os arquivos (documento_frente, selfie_documento, selfie_liveness) são obrigatórios."}), 400
    
    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    foto_doc_b64 = request.form.get('foto_documento_b64', '')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie_doc = request.files['selfie_documento']
    arquivo_selfie_liveness = request.files['selfie_liveness']

    logger.info(f'ONBOARDING com Score: Iniciando fluxo para {nome_cliente}')
    
    try:
        doc_frente_url = cloudinary.uploader.upload(arquivo_frente, folder="onboarding_docs").get('secure_url')
        selfie_doc_url = cloudinary.uploader.upload(arquivo_selfie_doc, folder="onboarding_selfies_docs").get('secure_url')
        selfie_liveness_url = cloudinary.uploader.upload(arquivo_selfie_liveness, folder="onboarding_selfies_liveness").get('secure_url')
    except Exception as e:
        logger.error(f"Erro no upload para o Cloudinary: {e}", exc_info=True)
        return jsonify({"erro": f"Falha no upload de imagens: {e}"}), 500
    
    arquivo_frente.seek(0); frente_bytes = arquivo_frente.read()
    arquivo_selfie_doc.seek(0); selfie_doc_bytes = arquivo_selfie_doc.read()
    arquivo_selfie_liveness.seek(0); selfie_liveness_bytes = arquivo_selfie_liveness.read()
    
    workflow_executado = {}
    status_geral = "APROVADO"
    
    etapas = {
        'receita_federal_pep': data_service.check_receita_federal_pep(cpf_cliente),
        'liveness_passivo': biometrics_service.check_liveness_passivo(selfie_liveness_bytes),
        'face_match_liveness': biometrics_service.check_facematch(foto_doc_b64, selfie_liveness_bytes),
        'face_match_selfie_com_documento': biometrics_service.check_facematch(foto_doc_b64, selfie_doc_bytes),
        'background_check': bgc_service.check_background(cpf_cliente, nome_cliente),
        'validacao_documento': document_service.validate_document(frente_bytes)
    }

    for nome_etapa, resultado in etapas.items():
        workflow_executado[nome_etapa] = resultado
        if resultado.get('status') != 'APROVADO':
            status_geral = "PENDENCIA"
            
    resposta_final = {"status_geral": status_geral, "workflow_executado": workflow_executado}
    
    score_result = score_service.calculate_risk_score(workflow_executado)
    resposta_final["risk_score"] = score_result
    
    try:
        nova_verificacao = Verificacao(
            tipo_verificacao='PF',
            status_geral=status_geral,
            doc_frente_url=doc_frente_url,
            selfie_url=selfie_liveness_url,
            dados_extra_json={'selfie_documento_url': selfie_doc_url},
            risk_score=score_result.get('score')
        )
        nova_verificacao.set_dados_entrada({'nome': nome_cliente, 'cpf': cpf_cliente})
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f"Verificação para {nome_cliente} salva com sucesso no BD com score {score_result.get('score')}.")
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}', exc_info=True)
        db.session.rollback()

    return jsonify(resposta_final), 200