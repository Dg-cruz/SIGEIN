"""Módulos e ações do sistema para a matriz de permissões por perfil."""

MODULOS = [
    ("dashboard", "Dashboard"),
    ("cad", "CAD — Central de Atendimento"),
    ("frota", "Gestão de Frota"),
    ("usuarios", "Usuários"),
    ("unidades", "Unidades"),
    ("produtos", "Produtos"),
    ("movimentacoes", "Movimentações"),
    ("estoque", "Estoque"),
    ("paiol", "Paiol"),
    ("segem", "SEGEM"),
    ("eprotocolo", "E-Protocolo"),
    ("logs", "Logs"),
    ("administracao", "Administração"),
]

ACOES = [
    ("visualizar", "Visualizar"),
    ("inserir", "Inserir"),
    ("editar", "Editar"),
    ("excluir", "Excluir"),
]

MODULO_KEYS = [m[0] for m in MODULOS]
ACAO_KEYS = [a[0] for a in ACOES]
