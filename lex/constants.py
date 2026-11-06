"""Constantes e rótulos em português usados nas telas."""

STATES = [
    "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA",
    "PB", "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
]

ROLES = {"cliente": "Cliente", "advogado": "Advogado", "admin": "Administrador"}

CASE_STATUS = {
    "aberto": "Aberto",
    "aguardando_advogado": "Aguardando advogado",
    "em_andamento": "Em andamento",
    "concluido": "Concluído",
    "cancelado": "Cancelado",
}

URGENCY = {"baixa": "Baixa", "media": "Média", "alta": "Alta", "urgente": "Urgente"}

MATCH_STATUS = {
    "sugerido": "Sugerido",
    "aceito": "Aceito",
    "recusado": "Recusado",
    "expirado": "Expirado",
}

FEE_TYPES = {
    "fixo": "Valor fixo",
    "por_hora": "Por hora",
    "exito": "Êxito (percentual)",
    "misto": "Misto (fixo + êxito)",
}

FEE_STATUS = {"proposta": "Proposta", "aceita": "Aceita", "recusada": "Recusada"}

APPOINTMENT_MODES = {"online": "Online", "presencial": "Presencial", "telefone": "Telefone"}

APPOINTMENT_STATUS = {
    "agendada": "Agendada",
    "confirmada": "Confirmada",
    "realizada": "Realizada",
    "cancelada": "Cancelada",
}

VERIFICATION = {
    "pendente": "Em análise",
    "verificado": "Verificado",
    "rejeitado": "Rejeitado",
    "suspenso": "Suspenso",
}

EVENT_TYPES = {
    "caso_criado": "Solicitação criada",
    "status_alterado": "Status alterado",
    "advogado_aceitou": "Advogado aceitou o caso",
}

ALLOWED_UPLOAD_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "txt", "doc", "docx"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024
STORAGE_BUCKET = "case-documents"
