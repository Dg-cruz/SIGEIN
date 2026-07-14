"""Constantes do módulo CAD (alinhadas ao SINESP CAD / GCM)."""

PRIORIDADES = (
    ("emergencia", "Emergência"),
    ("urgente", "Urgente"),
    ("rotina", "Rotina"),
)

STATUS_OCORRENCIA = (
    ("aberta", "Aberta"),
    ("em_atendimento", "Em atendimento"),
    ("aguardando_despacho", "Aguardando despacho"),
    ("empenhada", "Empenhada"),
    ("em_atendimento_campo", "Em atendimento no campo"),
    ("encerrada", "Encerrada"),
    ("cancelada", "Cancelada"),
)

CANAIS = (
    ("153", "153 — Guarda Municipal"),
    ("190", "190"),
    ("193", "193"),
    ("telefo", "Telefone"),
    ("presencial", "Presencial"),
    ("app", "Aplicativo"),
    ("alarme", "Alarme / monitoramento"),
    ("outro", "Outro"),
)

TIPOS_NATUREZA = (
    ("tipica", "Típica (possível ilícito)"),
    ("atipica", "Atípica (não criminal)"),
)

MEIOS_EMPREGADOS = (
    ("nao_houve", "Não houve"),
    ("arma_fogo", "Arma de fogo"),
    ("arma_branca", "Arma branca"),
    ("veiculo", "Veículo"),
    ("explosivo", "Explosivo"),
    ("objeto_contundente", "Objeto contundente"),
    ("documento", "Documentos"),
    ("outro", "Outro"),
)

# Catálogo inicial de naturezas (pode migrar para tabela depois)
NATUREZAS = (
    ("perturbacao", "Perturbação do sossego", "Ordem pública", "atipica"),
    ("averiguacao", "Averiguação", "Ordem pública", "atipica"),
    ("apoio", "Apoio institucional / escolta", "Apoio", "atipica"),
    ("transito", "Orientação / trânsito", "Trânsito", "atipica"),
    ("pessoa_desaparecida", "Pessoa desaparecida / localizada", "Pessoa", "atipica"),
    ("violencia_domestica", "Violência doméstica / familiar", "Pessoa", "tipica"),
    ("ameaca", "Ameaça", "Pessoa", "tipica"),
    ("lesao", "Lesão corporal", "Pessoa", "tipica"),
    ("roubo", "Roubo", "Patrimônio", "tipica"),
    ("furto", "Furto", "Patrimônio", "tipica"),
    ("dano", "Dano / depredação", "Patrimônio", "tipica"),
    ("posse_arma", "Porte / posse de arma", "Armas", "tipica"),
    ("drogas", "Entorpecentes", "Entorpecentes", "tipica"),
    ("outro", "Outra natureza", "Diversos", "atipica"),
)


def label_map(pairs):
    return {k: v for k, v in pairs}


PRIORIDADE_LABELS = label_map(PRIORIDADES)
STATUS_LABELS = label_map(STATUS_OCORRENCIA)
CANAL_LABELS = label_map(CANAIS)
TIPO_NATUREZA_LABELS = label_map(TIPOS_NATUREZA)
MEIO_LABELS = label_map(MEIOS_EMPREGADOS)
NATUREZA_POR_CODIGO = {c: {"nome": n, "grupo": g, "tipo": t} for c, n, g, t in NATUREZAS}

# Widgets personalizáveis do dashboard CAD
CAD_DASHBOARD_WIDGETS = (
    {
        "key": "total_hoje",
        "label": "Ocorrências de hoje",
        "subtitle": "Registradas no dia",
        "icon": "fa-calendar-day",
        "group": "Volume",
        "tone": "primary",
    },
    {
        "key": "em_atendimento",
        "label": "Em atendimento",
        "subtitle": "Com o operador",
        "icon": "fa-headset",
        "group": "Fila",
        "tone": "info",
    },
    {
        "key": "aguardando_despacho",
        "label": "Aguardando despacho",
        "subtitle": "Prontas para empenho",
        "icon": "fa-tower-broadcast",
        "group": "Fila",
        "tone": "warn",
    },
    {
        "key": "empenhadas",
        "label": "Empenhadas",
        "subtitle": "Com recurso a caminho",
        "icon": "fa-car-side",
        "group": "Fila",
        "tone": "info",
    },
    {
        "key": "emergencia",
        "label": "Emergências abertas",
        "subtitle": "Prioridade máxima",
        "icon": "fa-triangle-exclamation",
        "group": "Prioridade",
        "tone": "danger",
    },
    {
        "key": "urgentes",
        "label": "Urgentes abertas",
        "subtitle": "Prioridade alta",
        "icon": "fa-bolt",
        "group": "Prioridade",
        "tone": "warn",
    },
    {
        "key": "encerradas_hoje",
        "label": "Encerradas hoje",
        "subtitle": "Finalizadas no dia",
        "icon": "fa-circle-check",
        "group": "Volume",
        "tone": "ok",
    },
    {
        "key": "total_abertas",
        "label": "Total em aberto",
        "subtitle": "Não encerradas/canceladas",
        "icon": "fa-folder-open",
        "group": "Volume",
        "tone": "primary",
    },
    {
        "key": "canal_153",
        "label": "Canal 153 (hoje)",
        "subtitle": "Guarda Municipal",
        "icon": "fa-phone",
        "group": "Canais",
        "tone": "info",
    },
    {
        "key": "tipicas_hoje",
        "label": "Naturezas típicas (hoje)",
        "subtitle": "Possível ilícito",
        "icon": "fa-scale-balanced",
        "group": "Natureza",
        "tone": "warn",
    },
    {
        "key": "atipicas_hoje",
        "label": "Naturezas atípicas (hoje)",
        "subtitle": "Não criminal",
        "icon": "fa-comments",
        "group": "Natureza",
        "tone": "info",
    },
    {
        "key": "sem_endereco",
        "label": "Sem endereço completo",
        "subtitle": "Abertas sem logradouro",
        "icon": "fa-map-location-dot",
        "group": "Qualidade",
        "tone": "muted",
    },
)

CAD_DASHBOARD_WIDGETS_BY_KEY = {w["key"]: w for w in CAD_DASHBOARD_WIDGETS}
CAD_DASHBOARD_DEFAULT_KEYS = (
    "total_hoje",
    "em_atendimento",
    "aguardando_despacho",
    "emergencia",
    "urgentes",
    "encerradas_hoje",
)
