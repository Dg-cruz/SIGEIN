"""Constantes e enums do módulo Paiol."""

import enum


class CategoriaTipoMaterial(str, enum.Enum):
    ARMAMENTO = "armamento"
    MUNICOES_EXPLOSIVOS = "municoes_explosivos"
    SISTEMAS_OPTICOS = "sistemas_opticos"
    EPI = "epi"


CATEGORIA_TIPO_MATERIAL_LABELS = {
    CategoriaTipoMaterial.ARMAMENTO: "Armamentos De Porte e Portátil",
    CategoriaTipoMaterial.MUNICOES_EXPLOSIVOS: "Munições e Químicos",
    CategoriaTipoMaterial.SISTEMAS_OPTICOS: "Sistemas Ópticos e Eletrônicos",
    CategoriaTipoMaterial.EPI: "Equipamentos de Proteção Individual (EPI)",
}

CATEGORIA_TIPO_MATERIAL_DESCRICOES = {
    CategoriaTipoMaterial.ARMAMENTO: (
        "Pistolas, revólveres, espingardas, carabinas e rifles. "
        "Controlados por número de série e histórico individual de manutenção."
    ),
    CategoriaTipoMaterial.MUNICOES_EXPLOSIVOS: (
        "Projéteis, munições, químicos e artefatos correlatos."
    ),
    CategoriaTipoMaterial.SISTEMAS_OPTICOS: (
        "Óculos de visão noturna, miras a laser, telêmetros e sistemas de comunicação táticos."
    ),
    CategoriaTipoMaterial.EPI: (
        "Coletes balísticos, capacetes, escudos e máscaras de proteção química."
    ),
}

CATEGORIA_TIPO_PREFIX = {
    CategoriaTipoMaterial.ARMAMENTO.value: "ARM",
    CategoriaTipoMaterial.MUNICOES_EXPLOSIVOS.value: "MUN",
    CategoriaTipoMaterial.SISTEMAS_OPTICOS.value: "OPT",
    CategoriaTipoMaterial.EPI.value: "EPI",
}

MUNICAO_QUANTIDADE_TIPOS = [
    ("unidade", "Unidade"),
    ("caixa", "Caixa"),
]

MUNICAO_CAMPOS = [
    {
        "name": "nome_comercial",
        "label": "Descrição / Nome comercial",
        "type": "textarea",
        "required": True,
        "placeholder": "Ex.: MUNIÇÃO 9MM LUGER OGIVAL 115GR",
        "full_width": True,
    },
    {
        "name": "calibre",
        "label": "Calibre",
        "type": "text",
        "required": True,
        "placeholder": "Ex.: .38 SPL, 9 × 19 mm, .45 ACP",
    },
    {
        "name": "fabricante_marca",
        "label": "Fabricante / Marca",
        "type": "select",
        "required": True,
        "options_source": "fabricantes",
        "empty_label": "Nenhum fabricante cadastrado",
    },
    {
        "name": "lote",
        "label": "Lote",
        "type": "text",
        "required": True,
        "placeholder": "Informe o lote",
    },
    {
        "name": "validade",
        "label": "Validade",
        "type": "date",
        "required": True,
    },
    {
        "name": "quantidade",
        "label": "Quantidade",
        "type": "quantidade",
        "required": True,
        "full_width": True,
    },
]

# Campos exibidos no cadastro após selecionar a categoria (extensível por tipo)
CATEGORIA_TIPO_MATERIAL_CAMPOS = {
    CategoriaTipoMaterial.ARMAMENTO.value: [
        {
            "name": "especie",
            "label": "Espécie",
            "type": "select",
            "required": True,
            "options": ["Pistola", "Revólver", "Espingarda", "Carabina", "Rifle"],
        },
        {
            "name": "marca_fabricante",
            "label": "Marca / Fabricante",
            "type": "select",
            "required": True,
            "options_source": "fabricantes",
            "empty_label": "Nenhum fabricante cadastrado",
        },
        {
            "name": "modelo",
            "label": "Modelo",
            "type": "text",
            "required": True,
            "placeholder": "Ex.: PT G2C, TH40, Pump",
        },
        {
            "name": "numero_serie",
            "label": "Número de série",
            "type": "text",
            "required": True,
            "placeholder": "Chave de controle do armamento",
            "help": "Campo obrigatório e chave de controle.",
        },
        {
            "name": "calibre",
            "label": "Calibre",
            "type": "select",
            "required": True,
            "options_source": "calibres",
            "empty_label": "Nenhum calibre cadastrado em Munições e Químicos",
            "help": "Diâmetro do cano ou da munição utilizada.",
        },
    ],
    CategoriaTipoMaterial.MUNICOES_EXPLOSIVOS.value: MUNICAO_CAMPOS,
    CategoriaTipoMaterial.SISTEMAS_OPTICOS.value: [
        {
            "name": "especie",
            "label": "Espécie",
            "type": "text",
            "required": True,
            "placeholder": "Ex.: Visão noturna, mira laser, telêmetro, rádio tático",
        },
    ],
    CategoriaTipoMaterial.EPI.value: [
        {
            "name": "especie",
            "label": "Espécie",
            "type": "text",
            "required": True,
            "placeholder": "Ex.: Colete balístico, capacete, escudo, máscara química",
        },
    ],
}


class TipoMaterialPaiol(str, enum.Enum):
    ARMA = "arma"
    MUNICAO = "municao"
    EXPLOSIVO = "explosivo"
    ACESSORIO = "acessorio"


TIPO_MATERIAL_LABELS = {
    TipoMaterialPaiol.ARMA: "Armamentos De Porte e Portátil",
    TipoMaterialPaiol.MUNICAO: "Munição",
    TipoMaterialPaiol.EXPLOSIVO: "Explosivo",
    TipoMaterialPaiol.ACESSORIO: "Acessório",
}

MATERIAL_LIST_URLS = {
    TipoMaterialPaiol.ARMA.value: "/paiol/cadastro/materiais-belicos",
    TipoMaterialPaiol.MUNICAO.value: "/paiol/cadastro/municoes",
    TipoMaterialPaiol.EXPLOSIVO.value: "/paiol/cadastro/explosivos",
    TipoMaterialPaiol.ACESSORIO.value: "/paiol/cadastro/acessorios",
}


def material_list_url(tipo: str | None = None) -> str:
    if tipo:
        return MATERIAL_LIST_URLS.get(tipo, "/paiol/cadastro/materiais")
    return "/paiol/cadastro/materiais"


class TipoMovimentacaoPaiol(str, enum.Enum):
    ENTRADA = "entrada"
    SAIDA = "saida"
    TRANSFERENCIA = "transferencia"
    AJUSTE = "ajuste"
    INVENTARIO = "inventario"
    DISTRIBUICAO = "distribuicao"
    DEVOLUCAO = "devolucao"
    BAIXA = "baixa"
    DESTRUICAO = "destruicao"
    CAUTELA = "cautela"


TIPO_MOVIMENTO_LABELS = {
    TipoMovimentacaoPaiol.ENTRADA: "Entrada",
    TipoMovimentacaoPaiol.SAIDA: "Saída",
    TipoMovimentacaoPaiol.TRANSFERENCIA: "Transferência",
    TipoMovimentacaoPaiol.AJUSTE: "Ajuste",
    TipoMovimentacaoPaiol.INVENTARIO: "Inventário",
    TipoMovimentacaoPaiol.DISTRIBUICAO: "Distribuição",
    TipoMovimentacaoPaiol.DEVOLUCAO: "Devolução",
    TipoMovimentacaoPaiol.BAIXA: "Baixa",
    TipoMovimentacaoPaiol.DESTRUICAO: "Destruição",
    TipoMovimentacaoPaiol.CAUTELA: "Cautela",
}


class StatusRequisicaoPaiol(str, enum.Enum):
    RASCUNHO = "rascunho"
    PENDENTE = "pendente"
    APROVADA = "aprovada"
    REJEITADA = "rejeitada"
    PARCIAL = "parcial"
    ATENDIDA = "atendida"
    CANCELADA = "cancelada"


STATUS_REQUISICAO_LABELS = {
    StatusRequisicaoPaiol.RASCUNHO: "Rascunho",
    StatusRequisicaoPaiol.PENDENTE: "Pendente",
    StatusRequisicaoPaiol.APROVADA: "Aprovada",
    StatusRequisicaoPaiol.REJEITADA: "Rejeitada",
    StatusRequisicaoPaiol.PARCIAL: "Parcialmente atendida",
    StatusRequisicaoPaiol.ATENDIDA: "Atendida",
    StatusRequisicaoPaiol.CANCELADA: "Cancelada",
}

STATUS_REQUISICAO_LABELS_STR = {k.value: v for k, v in STATUS_REQUISICAO_LABELS.items()}


class StatusCautelaPaiol(str, enum.Enum):
    ATIVA = "ativa"
    PENDENTE = "pendente"
    BAIXADA = "baixada"


STATUS_CAUTELA_LABELS = {
    StatusCautelaPaiol.ATIVA: "Ativa",
    StatusCautelaPaiol.PENDENTE: "Pendente",
    StatusCautelaPaiol.BAIXADA: "Baixada",
}

STATUS_CAUTELA_LABELS_STR = {k.value: v for k, v in STATUS_CAUTELA_LABELS.items()}

CAUTELA_ABAS_EQUIPAMENTO = [
    {"key": "armamento", "label": "Armamento", "icon": "fa-crosshairs"},
    {"key": "municao", "label": "Munição", "icon": "fa-bullseye"},
    {"key": "acessorio_epi", "label": "Acessórios/EPI", "icon": "fa-shield-halved"},
    {"key": "sistemas_opticos", "label": "Sistemas Ópticos", "icon": "fa-binoculars"},
]

CAUTELA_CATEGORIAS_GRID = {
    "armamento": "armamento",
    "municao": "municao",
    "acessorio_epi": "acessorio_epi",
    "sistemas_opticos": "acessorio_epi",
}

# Catálogo de atalhos disponíveis na dashboard (qualquer item do menu Paiol)
PAIOL_MENU_CATALOG = [
    {"key": "cadastro.materiais-belicos", "url": "/paiol/cadastro/materiais-belicos", "label": "Armamentos De Porte e Portátil", "subtitle": "Armas de porte e portáteis", "icon": "fa-crosshairs", "group": "Cadastro"},
    {"key": "cadastro.municoes", "url": "/paiol/cadastro/municoes", "label": "Munições e Químicos", "subtitle": "Catálogo de munições e químicos", "icon": "fa-bullseye", "group": "Cadastro"},
    {"key": "cadastro.acessorios", "url": "/paiol/cadastro/acessorios", "label": "Acessórios", "subtitle": "Coletes, coldres e similares", "icon": "fa-toolbox", "group": "Cadastro"},
    {"key": "cadastro.tipos-material", "url": "/paiol/cadastro/tipos-material", "label": "Tipos de materiais", "subtitle": "Categorias e espécies de material", "icon": "fa-tags", "group": "Cadastro"},
    {"key": "cadastro.classes", "url": "/paiol/cadastro/classes", "label": "Classes de material", "subtitle": "Classificação e compatibilidade", "icon": "fa-layer-group", "group": "Cadastro"},
    {"key": "cadastro.fabricantes", "url": "/paiol/cadastro/fabricantes", "label": "Fabricantes", "subtitle": "Cadastro de fabricantes", "icon": "fa-industry", "group": "Cadastro"},
    {"key": "cadastro.fornecedores", "url": "/paiol/cadastro/fornecedores", "label": "Fornecedores", "subtitle": "Cadastro de fornecedores", "icon": "fa-truck", "group": "Cadastro"},
    {"key": "cadastro.depositos", "url": "/paiol/cadastro/depositos", "label": "Depósitos", "subtitle": "Paióis e armazéns", "icon": "fa-warehouse", "group": "Cadastro"},
    {"key": "cadastro.localizacoes", "url": "/paiol/cadastro/localizacoes", "label": "Localizações", "subtitle": "Posições nos depósitos", "icon": "fa-map-pin", "group": "Cadastro"},
    {"key": "cadastro.usuarios", "url": "/paiol/cadastro/usuarios-autorizados", "label": "Usuários autorizados", "subtitle": "Operadores habilitados", "icon": "fa-user-shield", "group": "Cadastro"},
    {"key": "estoque.entrada", "url": "/paiol/estoque/entrada", "label": "Entrada", "subtitle": "Recebimento no paiol", "icon": "fa-arrow-down", "group": "Estoque"},
    {"key": "estoque.saida", "url": "/paiol/estoque/saida", "label": "Saída", "subtitle": "Saída de material", "icon": "fa-arrow-up", "group": "Estoque"},
    {"key": "estoque.transferencia", "url": "/paiol/estoque/transferencia", "label": "Transferência", "subtitle": "Entre depósitos", "icon": "fa-right-left", "group": "Estoque"},
    {"key": "estoque.inventario", "url": "/paiol/estoque/inventario", "label": "Inventário", "subtitle": "Contagem física", "icon": "fa-clipboard-check", "group": "Estoque"},
    {"key": "estoque.ajustes", "url": "/paiol/estoque/ajustes", "label": "Ajustes", "subtitle": "Correções documentadas", "icon": "fa-sliders", "group": "Estoque"},
    {"key": "estoque.consulta", "url": "/paiol/estoque/consulta", "label": "Consulta de estoque", "subtitle": "Saldos atuais", "icon": "fa-magnifying-glass", "group": "Estoque"},
    {"key": "mov.cautela", "url": "/paiol/movimentacoes/cautela", "label": "Cautela", "subtitle": "Cautela de material", "icon": "fa-clipboard-list", "group": "Movimentações"},
    {"key": "mov.distribuicoes", "url": "/paiol/movimentacoes/distribuicoes", "label": "Distribuições", "subtitle": "Atendimento de requisições", "icon": "fa-share-from-square", "group": "Movimentações"},
    {"key": "mov.baixas", "url": "/paiol/movimentacoes/baixas", "label": "Baixas", "subtitle": "Baixa patrimonial", "icon": "fa-ban", "group": "Movimentações"},
    {"key": "mov.destruicao", "url": "/paiol/movimentacoes/destruicao", "label": "Destruição", "subtitle": "Processo de destruição", "icon": "fa-fire", "group": "Movimentações"},
    {"key": "mov.historico", "url": "/paiol/movimentacoes", "label": "Histórico", "subtitle": "Movimentações registradas", "icon": "fa-clock-rotate-left", "group": "Movimentações"},
    {"key": "seg.custodia", "url": "/paiol/seguranca/custodia", "label": "Cadeia de custódia", "subtitle": "Trilha de responsabilidade", "icon": "fa-link", "group": "Segurança"},
    {"key": "seg.auditoria", "url": "/paiol/seguranca/auditoria", "label": "Auditoria", "subtitle": "Alertas e conferência", "icon": "fa-magnifying-glass-chart", "group": "Segurança"},
    {"key": "seg.assinaturas", "url": "/paiol/seguranca/assinaturas", "label": "Assinatura digital", "subtitle": "Documentos críticos", "icon": "fa-signature", "group": "Segurança"},
    {"key": "seg.permissoes", "url": "/paiol/seguranca/permissoes", "label": "Permissões", "subtitle": "Controle de acesso", "icon": "fa-key", "group": "Segurança"},
    {"key": "seg.logs", "url": "/paiol/seguranca/logs", "label": "Logs", "subtitle": "Auditoria do módulo", "icon": "fa-clipboard-list", "group": "Segurança"},
    {"key": "relatorios", "url": "/paiol/relatorios", "label": "Relatórios", "subtitle": "Relatórios operacionais", "icon": "fa-chart-bar", "group": "Relatórios"},
]

PAIOL_MENU_BY_KEY = {item["key"]: item for item in PAIOL_MENU_CATALOG}
