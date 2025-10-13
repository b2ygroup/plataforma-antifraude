# app/onboarding/pf/routes.py
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
from app.services import bgc_service, biometrics_service, data_service, document_service, score_service
from app.decorators import require_api_key

bp = Blueprint('onboarding_pf', __name__)

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
        credentials_path = os.path.join(current_app.root_path, '..', 'google-credentials.json')
        if os.path.exists(credentials_path):
            os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
            client = vision.ImageAnnotatorClient()
        else:
            logger.error("Arquivo de credenciais do Google (google-credentials.json) não encontrado.")
            client = None
    return client

def analisar_documento_com_google_vision(doc_frente_bytes):
    logger = current_app.logger
    logger.info("OCR V10: Iniciando análise com regex de alta precisão para CNH...")
    try:
        client = get_vision_client()
        if client is None: return {"status": "ERRO_CONFIGURACAO", "motivo": "Serviço de OCR não configurado."}
        
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        if not response.text_annotations: return {"status": "REPROVADO_OCR", "motivo": "Não foi possível detetar texto no documento."}

        full_text_com_newlines = response.text_annotations[0].description
        logger.info(f"OCR V10: Texto completo extraído:\n---\n{full_text_com_newlines}\n---")
        
        dados_extraidos = {}
        
        # NOME: Padrão específico que procura o nome entre "NOME E SOBRENOME" e a próxima linha que parece ser um campo
        nome_match = re.search(r'(?:NOME E SOBRENOME|NOME)\n([A-Z\s\n]+?)\n(?:[A-Z]\n\d{2}/\d{2}/\d{4}|DOC DE IDENTIDADE|DATA)', full_text_com_newlines)
        if nome_match:
            nome = nome_match.group(1).replace('\n', ' ').strip()
            dados_extraidos['nome'] = re.sub(r'\s+', ' ', nome)

        # CPF: Padrão que busca o CPF formatado
        cpf_match = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text_com_newlines.replace('\n', ' '))
        if cpf_match:
            dados_extraidos['cpf'] = cpf_match.group(1)

        # DATA DE NASCIMENTO: Padrão que busca a data após a palavra "NASCIMENTO" em uma nova linha
        nasc_match = re.search(r'NASCIMENTO\s*\n\s*(\d{2}/\d{2}/\d{4})', full_text_com_newlines, re.IGNORECASE)
        if nasc_match:
            dados_extraidos['data_nascimento'] = nasc_match.group(1)
        
        campos_faltando = [campo for campo in ['nome', 'cpf', 'data_nascimento'] if campo not in dados_extraidos]

        if campos_faltando:
            motivo = f"Não foi possível extrair os seguintes campos: {', '.join(campos_faltando)}."
            logger.warning(f"OCR V10: Falha na extração. {motivo}")
            return {"status": "REPROVADO_OCR", "motivo": motivo}

        logger.info(f"OCR V10: Dados extraídos com sucesso: {dados_extraidos}")
        return {"status": "SUCESSO", "dados": dados_extraidos}
    except Exception as e:
        logger.error(f"OCR V10: Erro inesperado na função de análise: {e}", exc_info=True)
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
    except Exception as e:
        logger.error(f'Falha ao salvar no BD: {e}', exc_info=True)
        db.session.rollback()

    return jsonify(resposta_final), 200