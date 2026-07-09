"""Constantes e enums do módulo Paiol."""

import enum


class TipoMaterialPaiol(str, enum.Enum):
    ARMA = "arma"
    MUNICAO = "municao"
    EXPLOSIVO = "explosivo"
    ACESSORIO = "acessorio"


TIPO_MATERIAL_LABELS = {
    TipoMaterialPaiol.ARMA: "Arma / material bélico",
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

# Catálogo de atalhos disponíveis na dashboard (qualquer item do menu Paiol)
PAIOL_MENU_CATALOG = [
    {"key": "cadastro.materiais-belicos", "url": "/paiol/cadastro/materiais-belicos", "label": "Materiais bélicos", "subtitle": "Armas e material controlado", "icon": "fa-crosshairs", "group": "Cadastro"},
    {"key": "cadastro.municoes", "url": "/paiol/cadastro/municoes", "label": "Munições", "subtitle": "Catálogo de munições", "icon": "fa-bullseye", "group": "Cadastro"},
    {"key": "cadastro.explosivos", "url": "/paiol/cadastro/explosivos", "label": "Explosivos", "subtitle": "Explosivos e detonantes", "icon": "fa-bomb", "group": "Cadastro"},
    {"key": "cadastro.acessorios", "url": "/paiol/cadastro/acessorios", "label": "Acessórios", "subtitle": "Coletes, coldres e similares", "icon": "fa-toolbox", "group": "Cadastro"},
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
    {"key": "mov.requisicoes", "url": "/paiol/movimentacoes/requisicoes", "label": "Requisições", "subtitle": "Solicitações de material", "icon": "fa-file-circle-plus", "group": "Movimentações"},
    {"key": "mov.distribuicoes", "url": "/paiol/movimentacoes/distribuicoes", "label": "Distribuições", "subtitle": "Atendimento de requisições", "icon": "fa-share-from-square", "group": "Movimentações"},
    {"key": "mov.devolucoes", "url": "/paiol/movimentacoes/devolucoes", "label": "Devoluções", "subtitle": "Retorno ao paiol", "icon": "fa-rotate-left", "group": "Movimentações"},
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
