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
from app.services import bgc_service, biometrics_service

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
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'
        client = vision.ImageAnnotatorClient()
    return client

def analisar_documento_com_google_vision(doc_frente_bytes):
    logger = current_app.logger
    logger.info("OCR V5: Iniciando análise multidocumento com Google Vision AI...")
    try:
        client = get_vision_client()
        image = vision.Image(content=doc_frente_bytes)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        if not texts:
            return {"status": "REPROVADO_OCR", "motivo": "Não conseguimos ler os dados do documento."}

        full_text = texts[0].description.replace('\n', ' ')
        dados_extraidos = {}

        # --- MELHOR PRÁTICA: Múltiplos padrões de Regex para maior compatibilidade ---
        padroes = {
            'cpf': [r'(\d{3}\.\d{3}\.\d{3}-\d{2})', r'(\d{3} \d{3} \d{3} \d{2})'],
            'data_nascimento': [
                r'NASCIMENTO\s*(\d{2}/\d{2}/\d{4})',  # Padrão CNH
                r'Data de Nasc\s*[:\s]*(\d{2}/\d{2}/\d{4})',  # Padrão RG
                r'\b(\d{2}/\d{2}/(19[4-9]\d|200\d))\b' # Padrão genérico para datas de nascimento
            ],
            'nome': [
                r'NOME\s*([A-Z\s]+?)\s*(?:REGISTRO|CPF)', # Padrão CNH
                r'\bNOME\b\s*([A-Z\s]+)' # Padrão mais genérico
            ]
        }

        for campo, regex_list in padroes.items():
            for regex in regex_list:
                match = re.search(regex, full_text, re.IGNORECASE)
                if match:
                    # Limpa e formata o resultado
                    valor = match.group(1).strip()
                    if campo == 'nome':
                        # Remove quebras de linha substituídas e espaços extras
                        valor = re.sub(r'\s+', ' ', valor).strip()
                    dados_extraidos[campo] = valor
                    break # Pára no primeiro padrão que funcionar para o campo

        if 'nome' not in dados_extraidos or 'cpf' not in dados_extraidos or 'data_nascimento' not in dados_extraidos:
            logger.warning(f"OCR V5: Falha ao extrair todos os campos. Encontrado: {dados_extraidos}")
            return {"status": "REPROVADO_OCR", "motivo": "Não foi possível extrair nome, CPF e data de nascimento."}

        logger.info(f"OCR V5: Dados extraídos com sucesso: {dados_extraidos}")
        return {"status": "SUCESSO", "tipo_documento_identificado": "AUTO", "dados": dados_extraidos, "foto_3x4_base64": "..."}
    except Exception as e:
        logger.error(f"OCR V5: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO_API", "motivo": "Falha na comunicação com o serviço de IA."}


@bp.route('/extrair-ocr', methods=['POST'])
@require_api_key
def extrair_ocr():
    if 'documento_frente' not in request.files:
        return jsonify({"erro": "O arquivo 'documento_frente' é obrigatório."}), 400
    
    resultado_ocr = analisar_documento_com_google_vision(request.files['documento_frente'].read())
    
    if resultado_ocr.get('status') == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify(resultado_ocr), 400

@bp.route('/verificar', methods=['POST'])
@require_api_key
def verificar_pessoa_fisica():
    # ... (O restante do arquivo permanece o mesmo, pois a lógica de orquestração já está correta)
    logger = current_app.logger
    if 'documento_frente' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Arquivos 'documento_frente' e 'selfie' são obrigatórios."}), 400
    
    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    foto_doc_b64 = request.form.get('foto_documento_b64', '')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie = request.files['selfie']

    logger.info(f'ONBOARDING API-FIRST: Iniciando fluxo para {nome_cliente}')
    
    try:
        upload_result_doc = cloudinary.uploader.upload(arquivo_frente, folder="onboarding_docs")
        doc_frente_url = upload_result_doc.get('secure_url')
        upload_result_selfie = cloudinary.uploader.upload(arquivo_selfie, folder="onboarding_selfies")
        selfie_url = upload_result_selfie.get('secure_url')
    except Exception as e:
        logger.error(f"Erro no upload para o Cloudinary: {e}")
        return jsonify({"erro": f"Falha no upload de imagens: {e}"}), 500
    
    arquivo_frente.seek(0)
    arquivo_selfie.seek(0)
    selfie_bytes = arquivo_selfie.read()
    
    workflow_results = {}
    status_geral = "APROVADO"
    
    workflow_results['liveness_ativo'] = biometrics_service.check_liveness_ativo()
    workflow_results['liveness_passivo'] = biometrics_service.check_liveness_passivo(selfie_bytes)
    workflow_results['face_match'] = biometrics_service.check_facematch(foto_doc_b64, selfie_bytes)
    if workflow_results['face_match']['status'] != 'APROVADO':
        status_geral = "PENDENCIA"

    if os.environ.get('BGC_PROVIDER_API_KEY'):
        workflow_results['background_check'] = bgc_service.check_background(cpf_cliente, nome_cliente)
    else:
        logger.warning("BGC Service: Chave de API não encontrada. Usando simulação de BGC.")
        workflow_results['background_check'] = {"status": "NAO_EXECUTADO", "detalhes": "Serviço de BGC real não configurado."}
    
    if workflow_results.get('background_check', {}).get('status') != 'APROVADO':
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