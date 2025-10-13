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
# Importando TODOS os nossos serviços
from app.services import bgc_service, biometrics_service, data_service, document_service

bp = Blueprint('onboarding_pf', __name__)

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
    logger.info("OCR V7: Iniciando análise de documento com lógica aprimorada e correção de 'HABILITA'...")
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

        # CPF
        cpf_padroes = [r'(\d{3}\.\d{3}\.\d{3}-\d{2})', r'(\d{3} \d{3} \d{3} \d{2})']
        for padrao in cpf_padroes:
            match = re.search(padrao, full_text_flat)
            if match:
                dados_extraidos['cpf'] = match.group(1)
                break
        
        # Data de Nascimento
        nasc_padroes = [
            r'(?:DATA DE NASC|NASCIMENTO)\s*[:\s]*(\d{2}/\d{2}/\d{4})',
            r'\b(\d{2}/\d{2}/(?:19|20)\d{2})\b'
        ]
        for padrao in nasc_padroes:
            match = re.search(padrao, full_text_flat, re.IGNORECASE)
            if match:
                dados_extraidos['data_nascimento'] = match.group(1)
                break

        # NOVIDADE: Lógica de extração de Nome mais robusta, removendo "HABILITA"
        nome_padroes = [
            r'(?:NOME|NOME COMPLETO)\n*([A-Z\s]+?)(?=\s\s|NASCIMENTO|FILIAÇÃO|CPF|DOC|REGISTRO|$)', # Pega até 2 espaços, ou outro campo
            r'NOME\s*([A-Z\s]+?)(?=\s\s|NASCIMENTO|FILIAÇÃO|CPF|DOC|REGISTRO|$)', # Versão de linha única
        ]
        if 'nome' not in dados_extraidos:
             for padrao in nome_padroes:
                match = re.search(padrao, full_text_com_newlines, re.IGNORECASE) # Usa texto com newlines para nome
                if match:
                    nome = match.group(1).replace('\n', ' ').strip()
                    # Remove "HABILITA" e múltiplos espaços, caso apareçam
                    nome = re.sub(r'\bHABILITA\b', '', nome, flags=re.IGNORECASE).strip()
                    dados_extraidos['nome'] = re.sub(r'\s+', ' ', nome) # Normaliza múltiplos espaços
                    break

        if 'nome' not in dados_extraidos: campos_faltando.append('nome')
        if 'cpf' not in dados_extraidos: campos_faltando.append('cpf')
        if 'data_nascimento' not in dados_extraidos: campos_faltando.append('data_nascimento')

        if campos_faltando:
            motivo = f"Não foi possível extrair os seguintes campos: {', '.join(campos_faltando)}."
            logger.warning(f"OCR V7: Falha na extração. {motivo} Encontrado: {dados_extraidos}")
            return {"status": "REPROVADO_OCR", "motivo": motivo}

        logger.info(f"OCR V7: Dados extraídos com sucesso: {dados_extraidos}")
        return {"status": "SUCESSO", "tipo_documento_identificado": "AUTO", "dados": dados_extraidos, "foto_3x4_base64": "..."}
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
    # NOVIDADE: Verifica os novos campos de arquivo
    if 'documento_frente' not in request.files or 'selfie_documento' not in request.files or 'selfie_liveness' not in request.files:
        return jsonify({"erro": "Todos os arquivos (documento_frente, selfie_documento, selfie_liveness) são obrigatórios."}), 400
    
    # Input de dados
    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    foto_doc_b64 = request.form.get('foto_documento_b64', '')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie_doc = request.files['selfie_documento'] # NOVIDADE
    arquivo_selfie_liveness = request.files['selfie_liveness'] # NOVIDADE (Renomeado)

    logger.info(f'ONBOARDING V3 (idwall flow): Iniciando fluxo para {nome_cliente}')
    
    try:
        upload_result_doc = cloudinary.uploader.upload(arquivo_frente, folder="onboarding_docs")
        doc_frente_url = upload_result_doc.get('secure_url')
        # NOVIDADE: Upload da selfie com documento
        upload_result_selfie_doc = cloudinary.uploader.upload(arquivo_selfie_doc, folder="onboarding_selfies_docs")
        selfie_doc_url = upload_result_selfie_doc.get('secure_url')
        # NOVIDADE: Upload da selfie de liveness
        upload_result_selfie_liveness = cloudinary.uploader.upload(arquivo_selfie_liveness, folder="onboarding_selfies_liveness")
        selfie_liveness_url = upload_result_selfie_liveness.get('secure_url')
    except Exception as e:
        logger.error(f"Erro no upload para o Cloudinary: {e}", exc_info=True)
        return jsonify({"erro": f"Falha no upload de imagens de evidência: {e}"}), 500
    
    arquivo_frente.seek(0)
    frente_bytes = arquivo_frente.read()
    arquivo_selfie_doc.seek(0)
    selfie_doc_bytes = arquivo_selfie_doc.read() # NOVIDADE
    arquivo_selfie_liveness.seek(0)
    selfie_liveness_bytes = arquivo_selfie_liveness.read() # NOVIDADE
    
    workflow_results = {}
    status_geral = "APROVADO"
    
    # --- ORQUESTRAÇÃO DE SERVIÇOS SEGUINDO O FLUXO IDWALL ---

    # 1. Receita Federal + PEP
    rf_pep_result = data_service.check_receita_federal_pep(cpf_cliente)
    workflow_results['receita_federal_pep'] = rf_pep_result
    if rf_pep_result['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    # 2. Liveness Passivo (na selfie com documento, ou na selfie de liveness - vamos usar a de liveness para o passivo)
    liveness_passivo_result = biometrics_service.check_liveness_passivo(selfie_liveness_bytes)
    workflow_results['liveness_passivo'] = liveness_passivo_result
    if liveness_passivo_result['status'] != 'APROVADO': status_geral = "PENDENCIA"

    # 3. Face Match (entre a foto do documento, a selfie com documento e a selfie de liveness)
    # Vamos fazer o Face Match entre a foto do documento e a selfie com liveness para o desafio ativo
    face_match_liveness_result = biometrics_service.check_facematch(foto_doc_b64, selfie_liveness_bytes)
    workflow_results['face_match_liveness'] = face_match_liveness_result
    if face_match_liveness_result['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    # E um Face Match adicional para a selfie com documento (verificação de posse)
    face_match_doc_selfie_result = biometrics_service.check_facematch(foto_doc_b64, selfie_doc_bytes)
    workflow_results['face_match_selfie_com_documento'] = face_match_doc_selfie_result
    if face_match_doc_selfie_result['status'] != 'APROVADO': status_geral = "PENDENCIA"

    # 4. Background Check (BGC)
    bgc_result = bgc_service.check_background(cpf_cliente, nome_cliente)
    workflow_results['background_check'] = bgc_result
    if bgc_result['status'] != 'APROVADO': status_geral = "PENDENCIA"

    # 5. Validação do Documento (na foto do documento)
    validacao_doc_result = document_service.validate_document(frente_bytes)
    workflow_results['validacao_documento'] = validacao_doc_result
    if validacao_doc_result['status'] != 'APROVADO': status_geral = "PENDENCIA"

    resposta_final = {"status_geral": status_geral, "workflow_executado": workflow_results}
    
    try:
        nova_verificacao = Verificacao(
            tipo_verificacao='PF',
            status_geral=status_geral,
            doc_frente_url=doc_frente_url,
            selfie_url=selfie_liveness_url, # Usa a URL da selfie de liveness como principal
            dados_extra_url={'selfie_documento_url': selfie_doc_url} # NOVIDADE: Armazena URL extra
        )
        nova_verificacao.set_dados_entrada({'nome': nome_cliente, 'cpf': cpf_cliente})
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}', exc_info=True)
        db.session.rollback()

    return jsonify(resposta_final), 200