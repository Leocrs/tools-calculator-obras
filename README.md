# tools-calculator-obras-testes — Notas de cache

## Resumo rápido

Atualizei os decorators `@st.cache_data` neste módulo para usar TTL de 24 horas (86400 segundos). Isso reduz chamadas externas e melhora desempenho em produção.

## Arquivos modificados

- `main_interface.py`
  - `@st.cache_data(ttl=180, ...)` -> `@st.cache_data(ttl=86400, ...)`
- `data_services.py`
  - `get_monday_data`: `ttl=300` -> `ttl=7200` (2h)
  - `get_eap_data`: `ttl=600` -> `ttl=86400`
  - `load_incc_data`: `ttl=3600` -> `ttl=86400`
  - `get_siglas_eaps`: `ttl=300` -> `ttl=86400`

## Motivação

Dados como EAPs, projetos e índices INCC mudam com pouca frequência. TTL mais longo reduz latência e chamadas à API/DB. Se precisar de dados mais frescos para algum fluxo (ex.: dados do Monday.com), considere reduzir apenas esse TTL.

---

# TOOLS Calculator

Sistema para análise de obras com cálculos de INCC (Índice Nacional da Construção Civil).

## Estrutura do Projeto

```
tools-calculator-obras/
├── config_utils.py          # Configurações e utilitários
├── data_services.py         # Serviços de dados (MongoDB, Monday.com)
├── main_interface.py        # Interface principal da aplicação
├── incc_collector.py        # Coleta de dados do INCC
├── dados_dia01_indice.csv   # Base de dados histórica do INCC
├── requirements.txt         # Dependências do projeto
└── README.md               # Este arquivo
```

## Módulos

### 1. config_utils.py

- Configurações do sistema (MongoDB, Monday.com)
- Funções utilitárias para formatação de dados
- Cálculos de valores ajustados pelo INCC
- Configuração da interface Streamlit

### 2. data_services.py

- Integração com Monday.com
- Operações com MongoDB
- Processamento de dados de EAP
- Carregamento de dados do INCC

### 3. main_interface.py

- Interface principal do usuário
- Sistema de filtros
- Renderização de tabelas
- Funcionalidades de export

## Como Executar

1. Instale as dependências:

```bash
pip install -r requirements.txt
```

2. Execute a aplicação:

```bash
streamlit run main_interface.py
```

## Funcionalidades

- ✅ Análise de obras com filtros avançados
- ✅ Cálculos automáticos com correção pelo INCC
- ✅ Interface profissional e responsiva
- ✅ Export para Excel
- ✅ Cópia de dados para área de transferência
- ✅ Simulação de valores por área

## Tecnologias

- **Streamlit**: Interface web
- **Pandas**: Manipulação de dados
- **MongoDB**: Banco de dados
- **Monday.com**: Integração de projetos
- **BeautifulSoup**: Web scraping (INCC)
