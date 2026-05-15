# 🧭 SIGEN — Sistema Integrado de Gestão de Estoque e Inventário

![SIGEN](https://img.shields.io/badge/SIGEN-v1.0-0d6efd)
![FastAPI](https://img.shields.io/badge/FastAPI-✨-00a7c4)
![Jinja2](https://img.shields.io/badge/Jinja2-Templates-ff5b5b)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-DB-336791)

Aplicação web em FastAPI + Jinja2 para gerenciar equipamentos, unidades, usuários, movimentações e logs.

---

## 🎯 Visão geral
- Backend: FastAPI  
- Templates: Jinja2  
- Banco de dados: PostgreSQL (banco `sigein`)  
- Exportações: PDF (ReportLab) e XLSX (openpyxl)

## 🎨 Paleta de cores (interface)
| Cor | Variável | Hex |
|---:|:---:|:---:|
| 🟦 Azul Primário | --color-primary | #0d6efd |
| 🟩 Verde | --color-success | #198754 |
| 🟨 Amarelo | --color-warning | #ffc107 |
| 🟥 Vermelho | --color-danger | #dc3545 |
| ⬜ Fundo | --color-bg | #ffffff |
| ⚫ Texto | --color-text | #222222 |

---

## 📁 Estrutura principal do projeto
| Arquivo / Pasta | Descrição |
|---|---|
| main.py | Ponto de entrada da aplicação |
| requirements.txt | Dependências do projeto |
| database.py | Configuração do SQLAlchemy (PostgreSQL) / engine / get_db |
| dependencies.py | Sessões em memória e helpers (registrar_log, get_current_user) |
| models.py | Modelos ORM (User, Unit, Equipment, Movement, Log) |
| routers/ | Rotas organizadas por domínio (auth, dashboard, equipment, users, logs) |
| templates/ | Templates Jinja2 (views) |
| static/style.css | Estilos principais |
| init_db.py | Cria tabelas + seed |
| create_admin.py | Cria usuário administrador |
| create_tables.py | Recria tabelas (apaga dados) |
| auth.py | Helpers de hash (passlib) — integrar ao fluxo de persistência de senhas |

---

## 🚀 Rotas principais
| Método | Caminho | Descrição |
|---:|:---|:---|
| GET | /login | Formulário de login |
| POST | /login | Autenticar usuário |
| GET | /dashboard | Painel principal |
| GET | /equipment | Listagem de equipamentos |
| GET / POST | /equipment/add | Adicionar equipamento |
| GET / POST | /equipment/edit/{id} | Editar equipamento |
| GET / POST | /equipment/confirm_delete/{id} | Confirmar / excluir equipamento |
| GET | /users | CRUD de usuários |
| GET | /logs | Listar logs |
| GET | /logs/export/pdf | Exportar logs em PDF |
| GET | /logs/export/xlsx | Exportar logs em XLSX |

(Ver arquivos em `routers/` para detalhes de implementação.)

---

## ⚙️ Instalação (ambiente local)

### 1. Criar e ativar virtualenv

```powershell
python -m venv .venv
# PowerShell (Windows)
.\.venv\Scripts\Activate.ps1
# CMD (Windows)
.\.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

### 2. Instalar dependências

```powershell
pip install -r requirements.txt
pip install psycopg2-binary
```

O driver `psycopg2` é necessário para a conexão com PostgreSQL definida em `database.py`.

### 3. Preparar o PostgreSQL

O projeto usa PostgreSQL. A URL padrão em `database.py` é:

```
postgresql+psycopg2://postgres:1234@localhost:5432/sigein
```

Ajuste usuário, senha, host, porta ou nome do banco conforme seu ambiente.

Crie o banco antes de rodar os scripts de inicialização:

```sql
CREATE DATABASE sigein;
```

Certifique-se de que o serviço PostgreSQL está em execução em `localhost:5432`.

### 4. Criar tabelas e dados iniciais

```powershell
python init_db.py
```

> ⚠️ `init_db.py` executa `drop_all` e recria todas as tabelas, apagando dados existentes.

### 5. Criar apenas o administrador (opcional)

Se as tabelas já existirem e você só precisar do usuário admin:

```powershell
python create_admin.py
```

Credenciais padrão: usuário `admin`, senha `1234`.

### 6. Executar a aplicação

```powershell
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### 7. Acessar

Abra no navegador: **http://127.0.0.1:8000**

---

## 🧩 Observações e melhorias sugeridas

⚠️ **Senhas:** atualmente armazenadas em texto. Utilize hashing (funções em `auth.py`).

🧠 **Sessões:** gerenciadas via `SessionMiddleware` em `main.py`. Para produção, considere armazenamento persistente (Redis ou banco).

🧾 **Nomes inconsistentes** entre templates e modelos (`routers/equipment.py`) — revisar para unificação.

📦 **Exportações de logs** usam bibliotecas diferentes (ReportLab, openpyxl) — verificar versões.

🌍 **Idioma:** todas as rotas e templates estão em português — ajustar conforme público-alvo.

---

## 🤝 Contribuição / desenvolvimento

1. Crie uma nova branch  
2. Faça as alterações  
3. Teste localmente acessando as rotas  
4. Para recriar tabelas (⚠️ apaga dados):

```powershell
python create_tables.py
```

---

## 📜 Licença

Projeto sem licença especificada.  
Adicione um arquivo `LICENSE` conforme necessário.

---

## 📬 Contato

Abra uma issue ou pull request neste repositório para sugestões, correções ou dúvidas.
