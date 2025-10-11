# app/onboarding_pf/routes.py

import time
import random
from flask import Blueprint, request, jsonify, current_app
from app import db
from app.models import Verificacao

bp = Blueprint('onboarding_pf', __name__)


# --- ==================================================================== ---
# --- MOTOR DE VERIFICAÇÃO V2 - SIMULANDO AS FERRAMENTAS IDWALL           ---
# --- ==================================================================== ---

def simular_receita_federal_pep(cpf):
    """Simula a consulta na Receita Federal e a verificação de Pessoa Politicamente Exposta (PEP)."""
    current_app.logger.debug(f"MOCK (Receita Federal + PEP): Consultando CPF {cpf}...")
    time.sleep(0.5)
    # Simula se a pessoa é PEP
    is_pep = random.choice([True, False])
    return {
        "status": "SUCESSO",
        "dados": {
            "situacao_cadastral": "REGULAR",
            "nome_completo_rf": "Leonardo Alves da Silva",
            "pep": is_pep
        }
    }

def simular_liveness_passivo(selfie_bytes):
    """Simula a análise de Liveness Passivo para detectar fraudes como fotos de telas, máscaras, etc."""
    current_app.logger.debug("MOCK (Liveness Passivo): Analisando características do arquivo da selfie...")
    time.sleep(1)
    # Simula a detecção de uma fraude.
    # Em um caso real, essa análise seria muito mais complexa.
    if len(selfie_bytes) < 1000: # Simula uma imagem suspeita/pequena
        score = 0.3
        veredito = "REPROVADO"
        motivo = "Arquivo de imagem suspeito (tamanho baixo)"
    else:
        score = random.uniform(0.85, 0.99)
        veredito = "APROVADO"
        motivo = "Nenhum sinal de ataque por apresentação detectado."

    current_app.logger.debug(f"MOCK (Liveness Passivo): Veredito: {veredito}")
    return {"status": veredito, "score": score, "detalhes": motivo}

def simular_ocr(doc_bytes):
    """
    Simula um serviço de OCR inteligente que identifica o tipo de documento e extrai os dados.
    Reflete o fluxo da pág. 22 e as capacidades da pág. 18 da apresentação.
    """
    current_app.logger.debug("MOCK (OCR): Analisando e tipificando documento...")
    time.sleep(2)
    
    # Simula a identificação do tipo de documento
    tipo_documento = random.choice(["RG", "CNH"])
    
    if tipo_documento == "CNH":
        dados_extraidos = {
            "nome": "Leonardo A. Silva",
            "cpf": "111.222.333-44",
            "data_nascimento": "1995-08-10",
            "filiacao": "Maria da Silva",
            "numero_registro": "01234567890"
        }
    else: # RG
        dados_extraidos = {
            "nome": "Leonardo Alves da Silva",
            "rg": "12.345.678-9",
            "data_expedicao": "2015-01-20",
            "filiacao": "Maria da Silva / Joao da Silva",
            "cpf_no_rg": "111.222.333-44"
        }

    current_app.logger.debug(f"MOCK (OCR): Documento identificado como {tipo_documento}. Dados extraídos.")
    return {
        "status": "SUCESSO",
        "tipo_documento_identificado": tipo_documento,
        "dados": dados_extraidos,
        "foto_3x4_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
    }

def simular_face_match(foto_doc_base64, selfie_bytes):
    """Simula a comparação biométrica entre a foto do documento e a selfie."""
    current_app.logger.debug("MOCK (Face Match): Comparando biometria facial...")
    time.sleep(1)
    similaridade = random.uniform(0.90, 0.99)
    current_app.logger.debug(f"MOCK (Face Match): Similaridade de {similaridade * 100:.2f}% encontrada.")
    return {"status": "APROVADO", "similaridade": similaridade}

def simular_bgc(cpf, nome):
    """
    Simula o Background Check (BGC) com as fontes detalhadas na apresentação (pág. 22).
    """
    current_app.logger.debug(f"MOCK (BGC): Iniciando checagem de antecedentes para {nome}...")
    time.sleep(2)
    # Simula a descoberta de um mandado de prisão
    has_mandado_prisao = random.choice([True, False])
    
    detalhes = {
        "antecedentes_criminais": {"status": "NADA_CONSTA"},
        "listas_restritivas_ofac_onu_ue_uk": {"status": "NADA_CONSTA"},
        "mandados_prisao": {"status": "EM_ABERTO" if has_mandado_prisao else "NADA_CONSTA"},
        "risco_telefone_email_ip": {"score_risco": random.randint(1, 100)}
    }
    
    status_final_bgc = "PENDENCIA" if has_mandado_prisao else "APROVADO"
    current_app.logger.debug(f"MOCK (BGC): Checagem finalizada com status: {status_final_bgc}")
    return {"status": status_final_bgc, "detalhes": detalhes}

def simular_validacao_documento(doc_bytes, tipo_documento):
    """Simula a validação de legitimidade do documento (Documentoscopia / Dados Biométricos)."""
    current_app.logger.debug(f"MOCK (Validação Doc): Iniciando validação de legitimidade para {tipo_documento}...")
    time.sleep(1.5)
    
    if tipo_documento == "CNH":
        metodo = "Checagem de dados biométricos na base governamental"
    else: # RG
        metodo = "Análise por documentoscopia"
        
    current_app.logger.debug(f"MOCK (Validação Doc): Documento aprovado via {metodo}.")
    return {"status": "APROVADO", "metodo": metodo}


# --- ==================================================================== ---
# --- ENDPOINT PRINCIPAL: ORQUESTRADOR DO FLUXO DE ONBOARDING PF          ---
# --- ==================================================================== ---
@bp.route('/verificar', methods=['POST'])
def verificar_pessoa_fisica():
    logger = current_app.logger
    
    if 'documento' not in request.files or 'selfie' not in request.files:
        return jsonify({"erro": "Os arquivos 'documento' e 'selfie' são obrigatórios."}), 400

    nome_cliente = request.form.get('nome', 'N/A')
    cpf_cliente = request.form.get('cpf', 'N/A')
    arquivo_documento = request.files['documento']
    arquivo_selfie = request.files['selfie']
    
    logger.info(f'NOVO ONBOARDING PF: Iniciando fluxo para {nome_cliente} (CPF: {cpf_cliente})')

    documento_bytes = arquivo_documento.read()
    selfie_bytes = arquivo_selfie.read()

    # Este dicionário irá armazenar o resultado de cada etapa, como um workflow.
    workflow_results = {}
    status_geral = "APROVADO"

    # --- Executando o fluxo EXATAMENTE como na pág. 22 da apresentação ---

    # 1. Receita Federal + PEP
    workflow_results['receita_federal_pep'] = simular_receita_federal_pep(cpf_cliente)

    # 2. Liveness Passivo
    res_liveness = simular_liveness_passivo(selfie_bytes)
    workflow_results['liveness_passivo'] = res_liveness
    if res_liveness['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    # 3. OCR
    res_ocr = simular_ocr(documento_bytes)
    workflow_results['ocr'] = res_ocr
    if res_ocr['status'] != 'SUCESSO': status_geral = "PENDENCIA"
    
    # 4. Face Match
    foto_doc_b64 = res_ocr.get("foto_3x4_base64", "")
    res_facematch = simular_face_match(foto_doc_b64, selfie_bytes)
    workflow_results['face_match'] = res_facematch
    if res_facematch['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    # 5. BGC (Background Check)
    cpf_para_bgc = res_ocr.get("dados", {}).get("cpf", cpf_cliente)
    nome_para_bgc = res_ocr.get("dados", {}).get("nome", nome_cliente)
    res_bgc = simular_bgc(cpf_para_bgc, nome_para_bgc)
    workflow_results['background_check'] = res_bgc
    if res_bgc['status'] != 'APROVADO': status_geral = "PENDENCIA"
    
    # 6. Validação do Documento
    tipo_doc_identificado = res_ocr.get("tipo_documento_identificado", "DESCONHECIDO")
    res_validacao_doc = simular_validacao_documento(documento_bytes, tipo_doc_identificado)
    workflow_results['validacao_documento'] = res_validacao_doc
    if res_validacao_doc['status'] != 'APROVADO': status_geral = "PENDENCIA"

    # --- Consolidação, salvamento e resposta ---
    logger.info(f'Onboarding PF para CPF {cpf_cliente} finalizado com status GERAL: {status_geral}')
    
    resposta_final = {
        "status_geral": status_geral,
        "workflow_executado": workflow_results
    }
    
    try:
        nova_verificacao = Verificacao(tipo_verificacao='PF', status_geral=status_geral)
        dados_entrada = {'nome': nome_cliente, 'cpf': cpf_cliente}
        nova_verificacao.set_dados_entrada(dados_entrada)
        nova_verificacao.set_resultado_completo(resposta_final)
        db.session.add(nova_verificacao)
        db.session.commit()
        logger.info(f'Verificação do CPF {cpf_cliente} salva no banco de dados com ID: {nova_verificacao.id}')
    except Exception as e:
        logger.error(f'Falha ao salvar verificação do CPF {cpf_cliente} no banco de dados: {e}')
        db.session.rollback()

    return jsonify(resposta_final), 200

# O endpoint /extrair-ocr não é mais necessário, pois o fluxo agora é único e completo.
# Se quisermos mantê-lo, podemos, mas para seguir o fluxo do banco digital,
# a verificação completa é o ideal. Por clareza, vamos removê-lo por enquanto.