# 🎨 TintaControl – Sistema de Gestão de Estoque

Sistema web completo para controle de estoque de empresa de tintas.
Desenvolvido com **Python + Flask + PostgreSQL**.

---

## ✅ Funcionalidades

- 🔐 Login com autenticação segura (hash bcrypt)
- 🌙 Modo escuro / ☀️ Modo claro (com memória no navegador)
- 📊 Dashboard com KPIs em tempo real
- 📦 Cadastro de Produtos
- 📥 Entrada de Estoque (com markup automático)
- 📤 Saída de Estoque
- 📋 Relatório de Estoque + Exportar CSV
- 🛒 Pedido de Venda (com baixa automática no estoque)
- ❌ Cancelamento de Pedido (com restauração de estoque)
- 📝 Orçamento com impressão
- 🧾 Gerar NF-e / DANFE (simulação)
- 🗄️ Banco de Dados (visão consolidada de todos os registros)

---

## 🚀 Como rodar

### 1. Pré-requisitos
- Python 3.10+
- PostgreSQL rodando localmente

### 2. Criar o banco de dados
```sql
CREATE DATABASE tintacontrol;
```

### 3. Instalar dependências
```bash
cd tintacontrol
pip install -r requirements.txt
```

### 4. Configurar (opcional)
Crie um arquivo `.env` ou exporte as variáveis:
```bash
export DATABASE_URL="postgresql://postgres:SUA_SENHA@localhost:5432/tintacontrol"
export SECRET_KEY="sua-chave-secreta-aqui"
```

### 5. Rodar o sistema
```bash
python app.py
```

Acesse: **http://localhost:5000**

### 6. Login padrão
- Usuário: `admin`
- Senha: `admin123`

---

## 🗂️ Estrutura do Projeto

```
tintacontrol/
├── app.py                  # Aplicação Flask + Models + APIs
├── requirements.txt        # Dependências Python
├── README.md
└── templates/
    ├── base.html           # Layout base com sidebar + dark/light mode
    ├── login.html          # Tela de login
    ├── dashboard.html      # Dashboard com KPIs
    ├── produtos.html       # Cadastro de produtos
    ├── estoque_entrada.html
    ├── estoque_saida.html
    ├── estoque_relatorio.html
    ├── vendas_pedido.html
    ├── vendas_cancelamento.html
    ├── faturamento_orcamento.html
    ├── faturamento_nfe.html
    └── banco_dados.html
```

---

## 📐 Lógica de Markup

Na entrada de estoque:
```
Custo Unitário = Valor Total NF ÷ Quantidade
Preço de Venda = Custo Unitário × (1 + Markup% ÷ 100)
```

Exemplo: NF R$1.000, Qtd 10, Markup 15%
→ Custo = R$100,00
→ Venda = R$115,00

---

## 🔧 Próximas melhorias
- Cadastro de clientes/fornecedores
- Relatório de vendas por período
- Controle de estoque mínimo com alertas
- Integração real com SEFAZ (NF-e)
- Backup automático do banco
