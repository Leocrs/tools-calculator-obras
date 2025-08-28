# TOOLS Calculator

Sistema profissional para análise de obras com cálculos de INCC (Índice Nacional da Construção Civil).

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
