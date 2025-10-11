# app/onboarding_pf/routes.py

import time
import random
import os
import re
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao

# --- IMPORTAÇÃO DA BIBLIOTECA DA IA DO GOOGLE ---
from google.cloud import vision

# --- CONFIGURAÇÃO DA AUTENTICAÇÃO DO GOOGLE ---
# Garante que a aplicação use o arquivo de credencial que baixamos.
# É uma boa prática definir isso no início do arquivo que usa a API.
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google-credentials.json'

bp = Blueprint('onboarding_pf', __name__)

# --- ==================================================================== ---
# --- MOTOR DE VERIFICAÇÃO V6 - OCR REAL COM GOOGLE VISION AI             ---
# --- ==================================================================== ---

def analisar_cnh_com_google_vision(doc_frente_bytes):
    """
    Função REAL que envia a imagem de um documento para a Google Vision AI,
    recebe o texto extraído e o interpreta para encontrar campos de uma CNH.
    """
    logger = current_app.logger
    logger.info("OCR REAL: Enviando imagem para a Google Cloud Vision AI...")
    
    try:
        client = vision.ImageAnnotatorClient()
        image = vision.Image(content=doc_frente_bytes)
        
        # Chama a API de detecção de texto
        response = client.text_detection(image=image)
        texts = response.text_annotations

        if not texts:
            logger.warning("OCR REAL: Nenhum texto detectado pela IA.")
            return {"status": "REPROVADO", "motivo": "Nenhum texto pôde ser lido no documento."}

        # O primeiro resultado (texts[0]) é o texto completo, que usaremos para análise.
        full_text = texts[0].description
        logger.debug(f"OCR REAL: Texto completo extraído:\n{full_text}")

        # --- INTELIGÊNCIA: Interpretando o texto bruto com expressões regulares ---
        # Esta é uma implementação simples de parsing. Sistemas reais são mais complexos.
        dados_extraidos = {}
        
        # Procura por NOME
        match_nome = re.search(r'NOME\n(.+)', full_text)
        if match_nome:
            dados_extraidos['nome'] = match_nome.group(1).strip()
            
        # Procura por CPF
        match_cpf = re.search(r'(\d{3}\.\d{3}\.\d{3}-\d{2})', full_text)
        if match_cpf:
            dados_extraidos['cpf'] = match_cpf.group(1)

        # Procura por Nº REGISTRO
        match_registro = re.search(r'Nº REGISTRO\n(\d+)', full_text)
        if match_registro:
            dados_extraidos['numero_registro_cnh'] = match_registro.group(1).strip()
            
        # Procura por VALIDADE
        match_validade = re.search(r'VALIDADE\n(\d{2}/\d{2}/\d{4})', full_text)
        if match_validade:
            dados_extraidos['validade_cnh'] = match_validade.group(1)

        logger.info("OCR REAL: Dados da CNH parseados com sucesso.")
        return {
            "status": "SUCESSO",
            "tipo_documento_identificado": "CNH",
            "dados": dados_extraidos,
            "texto_bruto": full_text # Retornamos o texto completo para auditoria
        }
        
    except Exception as e:
        logger.error(f"OCR REAL: Erro ao chamar a API do Google Vision: {e}")
        return {"status": "ERRO", "motivo": "Falha na comunicação com o serviço de IA."}


# --- O RESTANTE DO BACKEND CONTINUA USANDO SIMULAÇÕES POR ENQUANTO ---
# (As funções de simulação individuais, exceto OCR, continuam as mesmas)
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

# --- ENDPOINT DE OCR ATUALIZADO PARA USAR A IA REAL ---
@bp.route('/extrair-ocr', methods=['POST'])
def extrair_ocr():
    logger = current_app.logger
    if 'documento_frente' not in request.files:
        return jsonify({"erro": "O arquivo 'documento_frente' é obrigatório."}), 400
    
    arquivo_frente = request.files['documento_frente']
    frente_bytes = arquivo_frente.read()
    
    # Chama a função REAL em vez da simulação
    resultado_ocr = analisar_cnh_com_google_vision(frente_bytes)
    
    if resultado_ocr['status'] == 'SUCESSO':
        return jsonify(resultado_ocr)
    else:
        return jsonify(resultado_ocr), 400

# --- ENDPOINT DE VERIFICAÇÃO FINAL (continua usando mocks para as outras etapas) ---
@bp.route('/verificar', methods=['POST'])
def verificar_pessoa_fisica():
    logger = current_app.logger
    if 'documento_frente' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Os arquivos 'documento_frente' e 'selfie' são obrigatórios."}), 400

    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    arquivo_frente = request.files['documento_frente']
    arquivo_selfie = request.files['selfie']
    frente_bytes = arquivo_frente.read()
    selfie_bytes = arquivo_selfie.read()

    workflow_results = {}
    status_geral = "APROVADO"
    
    # O fluxo de verificação final continua usando as outras simulações
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)
    workflow_results['liveness_ativo'] = simular_liveness_ativo()
    workflow_results['liveness_passivo'] = simular_liveness_passivo(selfie_bytes)
    workflow_results['validacao_documento_ia'] = simular_validacao_documento_ia(frente_bytes, b'')
    workflow_results['face_match'] = simular_face_match("", selfie_bytes)
    workflow_results['background_check'] = simular_bgc(cpf_cliente, nome_cliente)
    
    # Lógica para determinar o status_geral...
    for key, result in workflow_results.items():
        if result.get('status') != 'APROVADO' and result.get('status') != 'SUCESSO':
            status_geral = 'PENDENCIA'
            break

    resposta_final = { "status_geral": status_geral, "workflow_executado": workflow_results }
    
    # Salva no banco de dados
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