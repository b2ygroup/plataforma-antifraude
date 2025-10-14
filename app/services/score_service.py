# app/services/score_service.py

from flask import current_app

def calculate_risk_score(workflow_executado: dict):
    """
    Calcula um score de risco com base nos resultados do workflow de verificação.
    As regras e pesos abaixo são exemplos e devem ser ajustados conforme a necessidade do negócio.
    """
    logger = current_app.logger
    score = 500  # Score base (escala de 0 a 1000, por exemplo)
    reasons = []

    logger.info("SCORE_SERVICE: Iniciando cálculo de score de risco.")

    # 1. Análise de Face Match (Liveness vs. Documento)
    face_match = workflow_executado.get('face_match_liveness', {})
    if face_match.get('status') == 'APROVADO':
        similaridade = face_match.get('similaridade', 0)
        if similaridade > 0.98:
            score += 150
            reasons.append("+150: Altíssima similaridade no Face Match.")
        else:
            score += 75
            reasons.append("+75: Boa similaridade no Face Match.")
    else:
        score -= 200
        reasons.append("-200: Falha no Face Match principal.")

    # 2. Análise de Liveness Passivo
    liveness_passivo = workflow_executado.get('liveness_passivo', {})
    if liveness_passivo.get('status') == 'APROVADO':
        score += 100
        reasons.append("+100: Prova de vida passiva aprovada (selfie genuína).")
    else:
        score -= 150
        reasons.append("-150: Suspeita de fraude na prova de vida passiva.")

    # 3. Análise de Background Check (BGC)
    bgc = workflow_executado.get('background_check', {})
    if bgc.get('status') == 'PENDENCIA':
        score -= 250
        reasons.append("-250: Pendências encontradas no Background Check.")
    elif bgc.get('status') == 'APROVADO':
        score += 50
        reasons.append("+50: Nenhuma pendência encontrada no Background Check.")

    # 4. Análise da Validação do Documento
    validacao_doc = workflow_executado.get('validacao_documento', {})
    if validacao_doc.get('status') == 'APROVADO':
        score += 100
        reasons.append("+100: Documento validado com sucesso (sem indícios de fraude).")
    else:
        score -= 150
        reasons.append("-150: Documento com pendência na análise de autenticidade.")

    # Normaliza o score para ficar entre 0 e 1000
    score = max(0, min(score, 1000))

    # Define o rating com base em faixas de score
    if score >= 800:
        rating = "BAIXO RISCO"
    elif score >= 500:
        rating = "MÉDIO RISCO"
    else:
        rating = "ALTO RISCO"

    logger.info(f"SCORE_SERVICE: Cálculo finalizado. Score: {score}, Rating: {rating}")

    return {
        "score": score,
        "rating": rating,
        "reasons": reasons
    }