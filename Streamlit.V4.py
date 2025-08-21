# ====== IMPORTAÇÕES E CONFIGURAÇÕES INICIAIS ======
import streamlit as st
import pandas as pd
import requests
import json
import io
import os 
import re 
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Tuple, Optional
from pymongo import MongoClient
from bson import ObjectId

# ====== CONFIGURAÇÃO DE CONEXÃO COM O BANCO DE DADOS ======
MONGO_URI = "mongodb+srv://leonardocampos:leonardocampos@cluster0.7kdvlok.mongodb.net/ToolsConnect?retryWrites=true&w=majority"

# ====== CONFIGURAÇÃO DA API DO MONDAY ======
class APIConfig:
    API_KEY = 'eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjI2Njg4NzkwNiwiYWFpIjoxMSwidWlkIjoyMzA5NjM0MiwiaWFkIjoiMjAyMy0wNy0wNVQxNDoyNTo1NS4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6NDkwNjU3MCwicmduIjoidXNlMSJ9.tRWcVx3Q9oUEPKRMdaEiFzqCf1n0F7NelbjY09jQix4'
    BASE_URL = 'https://api.monday.com/v2'
    BOARD_ID = 926240878

# ====== FUNÇÃO DE CÁLCULO DE VALOR AJUSTADO PELO INCC ======
def calcular_valor_m2(custo, area, data_base, incc_df):
    if not area or area == 0:
        return None
    hoje = pd.to_datetime(datetime.now().date())
    data_base_dt = pd.to_datetime(data_base).date() if data_base else None
    if not data_base_dt or data_base_dt == hoje.date():
        return custo / area if data_base_dt else None
    data_retro = data_base_dt - relativedelta(months=2)
    incc_sorted = incc_df.sort_values('data')
    incc_retro = incc_sorted[incc_sorted['data'] <= pd.to_datetime(data_retro)]
    inccb = float(incc_retro.iloc[-1]['indice']) if not incc_retro.empty else float(incc_sorted.iloc[0]['indice'])
    incca = float(incc_sorted.iloc[-1]['indice'])
    return (custo * incca) / (inccb * area)

# Função utilitária única para tratamento de campos e formatação
def clean_and_format(val, tipo="str"):
    if pd.isna(val) or val is None or str(val).strip().lower() in ["nan", "none", ""]:
        return ""
    s = str(val).strip()
    if tipo == "sigla":
        for sep in ["-", " "]:
            if sep in s:
                return s.split(sep)[0].strip()
        return s
    if tipo == "reais":
        try:
            s = s.replace(" ", "")
            if s.count(",") == 1 and s.count(".") >= 1:
                s = s.replace(".", "").replace(",", ".")
            elif s.count(",") == 1:
                s = s.replace(",", ".")
            val_float = float(s)
            return f"R$ {val_float:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except:
            return s
    if tipo == "area":
        try:
            s = s.replace(" ", "")
            if "," in s and "." in s:
                s = s.replace(".", "").replace(",", ".")
            elif "," in s:
                s = s.replace(",", ".")
            return str(int(round(float(s))))
        except:
            return s
    if tipo == "json" and s.startswith("{") and s.endswith("}"):
        try:
            return json.dumps(eval(s), ensure_ascii=False)
        except:
            return s
    return s

def format_indice_incc(val, val_str=None):
    if val is None:
        return '—'
    try:
        val_num = float(val.replace('.', '').replace(',', '.')) if isinstance(val, str) else float(val)
        return f"{round(val_num, 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

def format_area_total(val):
    if val is None or not isinstance(val, (int, float)):
        return '—'
    return f"{int(round(val)):,}".replace(",", ".")

# ====== FUNÇÕES DE CONEXÃO COM O BANCO DE DADOS ======
@st.cache_resource
def get_mongo_client():
    return MongoClient(MONGO_URI)

def get_projetos_collection():
    return get_mongo_client()['ToolsConnect']['projetos']

def get_eaps_collection():
    return get_mongo_client()['ToolsConnect']['eaps']

# ====== FUNÇÃO PARA BUSCAR DADOS DO MONDAY.COM ======
@st.cache_data(ttl=300, show_spinner=False)
def get_monday_data() -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    query = f'''
    query {{
      boards(ids: [{APIConfig.BOARD_ID}]) {{
        name
        columns {{ id title type }}
        items_page(limit: 500) {{
          items {{
            id name
            column_values {{ id text column {{ title }} }}
          }}
        }}
      }}
    }}
    '''
    try:
        response = requests.post(
            APIConfig.BASE_URL, 
            json={'query': query}, 
            headers={'Authorization': APIConfig.API_KEY, 'Content-Type': 'application/json'}
        )
        if response.status_code != 200:
            st.error(f"Erro HTTP {response.status_code}")
            return None, None
        data = response.json()
        if 'errors' in data:
            st.error(f"Erro na API: {data['errors']}")
            return None, None
        board_info = data['data']['boards'][0]
        board_name = board_info['name']
        items = board_info['items_page']['items']
        columns = {col['id']: col['title'] for col in board_info['columns']}
        rows = []
        for item in items:
            row = {'id': item['id'], 'name': item['name']}
            for col_val in item['column_values']:
                col_title = columns.get(col_val['id'], col_val['id'])
                row[col_title] = col_val['text'] or ''
            rows.append(row)
        df = pd.DataFrame(rows)
        mapped_df = pd.DataFrame()
        mapped_df['Obras'] = df['name'] if 'name' in df.columns else df.get('Name', '')
        column_patterns = {
            'Construtora': ['CONSTRUTORA', 'EMPRESA', 'BUILDER', 'CONTRACTOR'],
            'Area': ['AREA', 'ÁREA', 'SIZE', 'TAMANHO'],
            'Local': ['LOCAL', 'LOCATION', 'ENDERECO', 'ENDEREÇO', 'ADDRESS'],
            'Arquitetura': ['ARQUITETURA', 'ARCHITECTURE', 'TIPO', 'TYPE', 'STYLE']
        }
        for field, patterns in column_patterns.items():
            mapped_df[field] = ''
            for col in df.columns:
                if any(pattern in col.upper() for pattern in patterns):
                    mapped_df[field] = df[col]
                    break
        mapped_df['Data'] = ''
        for col in df.columns:
            if 'TIMELINE' in col.upper():
                def extrair_data_inicio(val):
                    if not val or pd.isna(val):
                        return ''
                    partes = str(val).split('-')
                    if len(partes) >= 1:
                        data_str = partes[0].strip()
                        try:
                            dt = pd.to_datetime(data_str, errors='coerce')
                            return dt.strftime('%d/%m/%Y') if pd.notna(dt) else data_str
                        except:
                            return data_str
                    return val
                mapped_df['Data'] = df[col].apply(extrair_data_inicio)
                break
        if 'Area' in mapped_df.columns:
            def convert_area(area_str):
                if not area_str or pd.isna(area_str):
                    return 0.0
                try:
                    return float(str(area_str).replace('.', '').replace(',', '.'))
                except:
                    return 0.0
            mapped_df['Area_Numeric'] = mapped_df['Area'].apply(convert_area)
            mapped_df['Area_Display'] = mapped_df['Area']
        return board_name, mapped_df
    except Exception as e:
        st.error(f"Erro ao conectar com Monday.com: {e}")
        return None, None

# ====== CONFIGURAÇÃO DE LAYOUT E ESTILO DA PÁGINA ======
def setup_page():
    st.set_page_config(
        page_title="TOOLS",
        page_icon="🏗️",
        layout="wide",
        initial_sidebar_state="collapsed"
    )
    st.markdown(f"""
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate, max-age=0">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Source+Sans+3:wght@300;400;500;600;700&display=swap');
        .stApp {{ background-color: #ffffff !important; color: #262730 !important; }}
        .main {{ padding-top: 0rem; background-color: #ffffff !important; font-family: "Source Sans 3", sans-serif; }}
        .block-container {{ background-color: #ffffff !important; padding-top: 0rem; max-width: 100%; }}
        .header-container {{ background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e5e7eb; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; }}
        .tools-title {{ color: #0e938e; font-size: 3rem; font-weight: 700; letter-spacing: -2px; margin: 0; font-family: "Source Sans 3", sans-serif; }}
        .tabs-container {{ border-bottom: 2px solid #0e938e; margin-bottom: 2rem; padding-left: 2rem; }}
        .tab-active {{ display: inline-block; padding: 0.75rem 0; margin-right: 3rem; color: #0e938e; font-weight: 600; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 3px solid #0e938e; font-family: "Source Sans 3", sans-serif; }}
        .filters-section {{ padding: 0 2rem; margin-bottom: 1.5rem; }}
        .filter-label {{ color: #6b7280; font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.25rem; font-family: "Source Sans 3", sans-serif; }}
        .stTextInput > div > div > input {{ border: 1px solid #d1d5db !important; border-radius: 6px !important; background: white !important; font-size: 0.875rem !important; padding: 0.5rem 0.75rem !important; font-family: "Source Sans 3", sans-serif !important; color: #374151 !important; }}
        .stMultiSelect > div > div {{ border: 1px solid #d1d5db !important; border-radius: 6px !important; font-family: "Source Sans 3", sans-serif !important; background: #f9fafb !important; }}
        .stSlider > div > div > div > div {{ background-color: #0e938e !important; }}
        .metrics-container {{ display: flex; gap: 2rem; margin: 1.5rem 2rem; align-items: flex-start; }}
        .metric-simple {{ background: #ffffff; border: 2px solid #d1d5db; border-radius: 8px; padding: 1.5rem; text-align: center; box-shadow: 0 2px 8px rgba(0,0,0,0.1); min-width: 180px; flex: 1; }}
        .metric-label {{ color: #6b7280; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 0.75rem; font-family: "Source Sans 3", sans-serif; }}
        .metric-value {{ color: #1f2937; font-size: 2rem; font-weight: 700; margin: 0; font-family: "Source Sans 3", sans-serif; line-height: 1; }}
        .table-container {{ margin: 0 2rem; }}
        button[kind="secondary"] {{ background-color: white !important; border: 1px solid #0e938e !important; color: #0e938e !important; border-radius: 6px !important; }}
        #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}} .stDeployButton {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

# ====== RENDERIZAÇÃO DO CABEÇALHO DA PÁGINA ======
def render_header():
    st.markdown('''
    <div class="header-container">
        <div class="tools-title">TOOLS</div>
    </div>
    <div class="tabs-container">
        <span class="tab-active">TLS-001 RECURSOS E TIMELINE DO PROJETO</span>
    </div>
    ''', unsafe_allow_html=True)

# ====== CRIAÇÃO DOS FILTROS MULTISELECT ======
def create_multiselect_filter(label, options_base, key):
    options = options_base
    if key not in st.session_state:
        st.session_state[key] = []
    st.multiselect(
        "",
        options,
        key=key,
        label_visibility="collapsed",
        placeholder="Escolha uma opção"
    )
    # Se o filtro de OBRAS estiver vazio, retorna todas as opções
    if key == "obras" and not st.session_state[key]:
        return options_base
    return st.session_state[key]

# ====== RENDERIZAÇÃO DOS FILTROS PRINCIPAIS ======
def render_filters(df_eaps, siglas_eaps):
    st.markdown('<div class="filters-section">', unsafe_allow_html=True)
    if "modo_filtro" not in st.session_state:
        st.session_state["modo_filtro"] = "Qualquer critério (OU/União)"
    filtro_modo = st.radio(
        "Modo de combinação dos filtros:",
        ["Todos os critérios (E/Interseção)", "Qualquer critério (OU/União)"],
        horizontal=True,
        key="modo_filtro"
    )
    # Interdependência dos filtros: aplica todos os filtros no DataFrame para gerar opções dinâmicas
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    # Inicialização dos filtros
    obras_filter = st.session_state.get("obras", [])
    construtora_filter = st.session_state.get("construtora", [])
    arquitetura_filter = st.session_state.get("arquitetura", [])
    local_filter = st.session_state.get("local", "")

    # Aplica os filtros no DataFrame para gerar as opções dinâmicas
    df_filtrado = df_eaps.copy()
    if obras_filter:
        df_filtrado = df_filtrado[df_filtrado['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in obras_filter)]
    if construtora_filter:
        df_filtrado = df_filtrado[df_filtrado['Construtora'].astype(str).str.strip().str.lower().isin([str(x).strip().lower() for x in construtora_filter])]
    if arquitetura_filter:
        df_filtrado = df_filtrado[df_filtrado['Arquitetura'].astype(str).str.strip().str.lower().isin([str(x).strip().lower() for x in arquitetura_filter])]
    if local_filter:
        df_filtrado = df_filtrado[df_filtrado['Local'].astype(str).str.strip().str.lower() == str(local_filter).strip().lower()]

    # Opções sempre baseadas no DataFrame original, não filtrado
    obras_opcoes = sorted(df_eaps['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla")).unique().tolist())
    construtora_opcoes = sorted([x for x in df_eaps['Construtora'].dropna().astype(str).str.strip().unique().tolist() if x])
    arquitetura_opcoes = sorted(df_eaps['Arquitetura'].dropna().astype(str).str.strip().unique().tolist())
    locais_opcoes = sorted(df_eaps['Local'].dropna().astype(str).str.strip().unique().tolist())

    with col1:
        st.markdown('<div class="filter-label">ÁREA (m²)</div>', unsafe_allow_html=True)
        area_range = None
        if 'Area_Numeric' in df_filtrado.columns:
            valid_areas = df_filtrado['Area_Numeric'].dropna()
            if not valid_areas.empty:
                min_area = 0
                max_area = int(valid_areas.max()) if pd.notna(valid_areas.max()) else 0
                area_range = st.slider(
                    "", min_value=min_area, max_value=max_area, value=(min_area, max_area),
                    step=100, key="area", label_visibility="collapsed", format="%d m²"
                )
    with col2:
        st.markdown('<div class="filter-label">LOCAL</div>', unsafe_allow_html=True)
        local_filter = st.selectbox(
            "", options=locais_opcoes, key="local",
            placeholder="Escolha uma opção", label_visibility="collapsed", index=None
        )
    with col3:
        st.markdown('<div class="filter-label">OBRAS</div>', unsafe_allow_html=True)
        obras_filter = create_multiselect_filter("", obras_opcoes, "obras")
    with col4:
        st.markdown('<div class="filter-label">CONSTRUTORA</div>', unsafe_allow_html=True)
        construtora_filter = create_multiselect_filter("", construtora_opcoes, "construtora")
    with col5:
        st.markdown('<div class="filter-label">ARQUITETURA</div>', unsafe_allow_html=True)
        arquitetura_filter = create_multiselect_filter("", arquitetura_opcoes, "arquitetura")
    with col6:
        st.markdown('<div class="filter-label">Simular valores para área (m²):</div>', unsafe_allow_html=True)
        area_simulada = st.text_input(
            "",
            value="",
            placeholder="Digite uma área para simulação (opcional)",
            key="area_simulada",
            label_visibility="collapsed"
        )
        area_simulada_val = None
        if area_simulada:
            try:
                area_simulada_val = float(str(area_simulada).replace('.', '').replace(',', '.'))
            except:
                st.warning("Área simulada inválida. Use apenas números.")
        else:
            area_simulada_val = None
    st.markdown('</div>', unsafe_allow_html=True)
    return {
        'modo': filtro_modo,
        'area_range': area_range,
        'local': local_filter,
        'obras': obras_filter,
        'construtora': construtora_filter,
        'arquitetura': arquitetura_filter,
        'area_simulada_val': area_simulada_val
    }

# ====== FILTRO E APLICAÇÃO DOS FILTROS NO DATAFRAME ======
def apply_filters(df_eaps, filters, siglas_eaps):
    filtered_df = df_eaps.copy()
    filtro_aplicado = False
    if 'Area_Numeric' in df_eaps.columns and filters['area_range'] is not None:
        filtered_df = filtered_df[
            (filtered_df['Area_Numeric'] >= filters['area_range'][0]) & 
            (filtered_df['Area_Numeric'] <= filters['area_range'][1])
        ]
        filtro_aplicado = True
    if filters['local']:
        filtered_df = filtered_df[filtered_df['Local'].str.contains(filters['local'], case=False, na=False)]
        filtro_aplicado = True

    # Se filtro de obras está vazio, retorna DataFrame vazio
    if filters['obras'] is not None and len(filters['obras']) == 0 and 'Obras' in df_eaps.columns:
        return filtered_df.iloc[0:0], True

    if filters['modo'] == "Todos os critérios (E/Interseção)":
        if filters['obras'] and len(filters['obras']) > 0 and 'Obras' in df_eaps.columns:
            if len(filters['obras']) == 1:
                filtered_df = filtered_df[filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") == filters['obras'][0])]
            else:
                filtered_df = filtered_df.iloc[0:0]
            filtro_aplicado = True
        # Filtro de construtora e arquitetura: aplica apenas se houver seleção
        for filter_key, column in [('construtora', 'Construtora'), ('arquitetura', 'Arquitetura')]:
            if filters[filter_key] and len(filters[filter_key]) > 0 and column in df_eaps.columns:
                # Filtra ignorando caixa e espaços
                selected = [str(x).strip().lower() for x in filters[filter_key]]
                filtered_df = filtered_df[
                    filtered_df[column].astype(str).str.strip().str.lower().isin(selected)
                ]
                filtro_aplicado = True
    else:
        indices = set()
        if filters['obras'] and len(filters['obras']) > 0 and 'Obras' in df_eaps.columns:
            indices_obras = set(filtered_df[filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in filters['obras'])].index)
            indices.update(indices_obras)
        for filter_key, column in [('construtora', 'Construtora'), ('arquitetura', 'Arquitetura')]:
            if filters[filter_key] and len(filters[filter_key]) > 0 and column in df_eaps.columns:
                mask = filtered_df[column].astype(str).str.upper().str.contains(
                    '|'.join([term.upper() for term in filters[filter_key]]), na=False
                )
                indices.update(set(filtered_df[mask].index))
        if indices:
            filtered_df = filtered_df.loc[list(indices)]
            filtro_aplicado = True
    return filtered_df, filtro_aplicado

# ====== BUSCA E TRATAMENTO DOS DADOS DE EAP E PROJETOS ======
def get_eap_data():
    eaps_collection = get_eaps_collection()
    projetos_collection = get_projetos_collection()
    eaps_dados = list(eaps_collection.find({}))
    def clean_mongo_field(val):
        if val is None or pd.isna(val) or str(val).strip().lower() in ['none', 'nan', '']:
            return ''
        return str(val).strip()
    projetos_dados = {}
    for p in projetos_collection.find({}):
        projeto_tratado = {k: clean_mongo_field(v) for k, v in p.items()}
        sigla = projeto_tratado.get("sigla", "")
        nome = projeto_tratado.get("nome", "Projeto sem nome")
        projetos_dados[str(p["_id"])] = {"sigla": sigla, "nome": nome}
    return eaps_dados, projetos_dados

# ====== PROCESSAMENTO DA MATRIZ EAP ======
def process_eap_matrix(eaps_dados, projetos_dados, selected_obras, monday_df, incc_df_eap, area_simulada_val=None):
    siglas_obras_eap = set()
    data_ref_dict = {}
    area_m2_dict_monday = {}
    for doc in eaps_dados:
        projeto_info = projetos_dados.get(doc.get("projeto_id"), {"sigla": "", "nome": "Obra não encontrada"})
        sigla_obra = projeto_info["sigla"] or projeto_info["nome"]
        siglas_obras_eap.add(sigla_obra)
        data_ref_dict[sigla_obra] = doc.get("dataBase", "")
    if monday_df is not None and not monday_df.empty:
        for idx, row in monday_df.iterrows():
            nome_obra = str(row['Obras']).strip()
            area_obra = str(row['Area']).strip() if 'Area' in row else ''
            if nome_obra:
                area_m2_dict_monday[nome_obra] = area_obra
    matriz_final = []
    area_row = {"CÓDIGO": "", "DESCRIÇÃO": "ÁREA M²"}
    if selected_obras:
        for obra in selected_obras:
            area_val = area_m2_dict_monday.get(obra, None)
            if not area_val or str(area_val).strip().lower() in ["", "nan", "none"]:
                for nome_monday, area_monday in area_m2_dict_monday.items():
                    if obra.lower() in nome_monday.lower():
                        area_val = area_monday
                        break
            area_row[obra] = clean_and_format(area_val, tipo="area") if area_val else ""
        area_row["Média"] = ""
    matriz_final.append(area_row)
    dataref_row = {"CÓDIGO": "", "DESCRIÇÃO": "DATA BASE"}
    if selected_obras:
        for sigla in selected_obras:
            dataref_row[sigla] = str(data_ref_dict.get(sigla, ""))
        dataref_row["Média"] = ""
    matriz_final.append(dataref_row)
    codigos = set()
    descricoes = {}
    grupo_dict = {}
    for doc in eaps_dados:
        projeto_info = projetos_dados.get(doc.get("projeto_id"), {"sigla": "", "nome": "Obra não encontrada"})
        sigla_obra = projeto_info["sigla"] or projeto_info["nome"]
        itens = doc.get("itens", [])
        itens_nivel_1 = [item for item in itens if item.get("nivel") == 1]
        for item in itens_nivel_1:
            codigo = item.get("codEAP", "")
            descricao = item.get("descricao", "")
            preco_m2 = item.get("preco_m2", "") if "preco_m2" in item else item.get("preco", "")
            codigos.add(codigo)
            descricoes[codigo] = descricao
            chave = (codigo, descricao)
            if chave not in grupo_dict:
                grupo_dict[chave] = {}
            grupo_dict[chave][sigla_obra] = preco_m2
    for codigo in sorted(codigos):
        desc_original = descricoes.get(codigo, "")
        desc_limpa = re.sub(r"^Item\s*", "", desc_original, flags=re.IGNORECASE)
        desc_limpa = re.sub(r"\s+", " ", desc_limpa).strip()
        linha = {"CÓDIGO": codigo, "DESCRIÇÃO": desc_limpa}
        valores_obras = []
        valores_formatados = []
        if selected_obras:
            for sigla in selected_obras:
                valor = grupo_dict.get((codigo, descricoes.get(codigo, "")), {}).get(sigla, "")
                valor_final = valor
                if incc_df_eap is not None and valor and str(valor).strip() not in ['', 'nan', 'none']:
                    try:
                        val_str = re.sub(r"[^0-9.,]", "", str(valor))
                        if val_str:
                            if "," in val_str:
                                val_str = val_str.replace(".", "").replace(",", ".")
                            custo_raw = float(val_str)
                            data_base_obra = data_ref_dict.get(sigla, "")
                            area_obra_str = area_m2_dict_monday.get(sigla, "")
                            if not area_obra_str:
                                for nome_monday, area_monday in area_m2_dict_monday.items():
                                    if sigla.lower() in nome_monday.lower():
                                        area_obra_str = area_monday
                                        break
                            try:
                                if area_obra_str and str(area_obra_str).strip():
                                    area_real = float(str(area_obra_str).replace('.', '').replace(',', '.'))
                                else:
                                    area_real = 1.0
                            except:
                                area_real = 1.0
                            
                            # Calcular valor unitário para a área real
                            valor_unitario_real = calcular_valor_m2(custo_raw, area_real, data_base_obra, incc_df_eap)
                            
                            # Se há área simulada, aplicar a regra de três
                            if area_simulada_val and area_simulada_val > 0:
                                valor_final = valor_unitario_real * area_simulada_val 
                            else:
                                valor_final = valor_unitario_real
                    except:
                        valor_final = valor
                linha[sigla] = f"{valor_final:.2f}".replace(".", ",") if valor_final not in [None, ""] else ""
                valores_formatados.append(valor_final)
                try:
                    if isinstance(valor_final, (int, float)):
                        valores_obras.append(float(valor_final))
                    else:
                        val_str = re.sub(r"[^0-9.,]", "", str(valor_final))
                        if val_str:
                            if "," in val_str:
                                val_str = val_str.replace(".", "").replace(",", ".")
                            valores_obras.append(float(val_str))
                except:
                    pass
        tem_valor = any(v not in [None, "", 0] for v in valores_formatados)
        if tem_valor:
            if valores_obras:
                media = sum(valores_obras) / len(valores_obras)
                linha["Média"] = f"{media:.2f}".replace(".", ",")
            else:
                linha["Média"] = ""
            matriz_final.append(linha)
    return matriz_final

# ====== RENDERIZAÇÃO DA SEÇÃO EAP (TABELA PRINCIPAL) ======
def render_eap_section(selected_obras, area_simulada_val=None):
    try:
        eaps_dados, projetos_dados = get_eap_data()
        script_dir_eap = os.path.dirname(os.path.abspath(__file__))
        incc_path_eap = os.path.join(script_dir_eap, 'dados_dia01_indice.csv')
        incc_df_eap = None
        try:
            incc_df_eap = pd.read_csv(incc_path_eap, sep=',', decimal='.', encoding='utf-8', parse_dates=['data'], dayfirst=True)
            incc_df_eap = incc_df_eap.sort_values('data')
            incc_df_eap = incc_df_eap[pd.to_numeric(incc_df_eap['indice'], errors='coerce').notnull()]
        except:
            incc_df_eap = None
        if eaps_dados:
            board_name, monday_df = get_monday_data()
            matriz_final = process_eap_matrix(
                eaps_dados, projetos_dados, selected_obras, monday_df, incc_df_eap, area_simulada_val
            )
            nome_codigo, nome_descricao = "Código", "Descrição"
            selecao_padrao = [True] * len(matriz_final)
            if 'selecao_linhas' not in st.session_state or len(st.session_state['selecao_linhas']) != len(matriz_final):
                st.session_state['selecao_linhas'] = selecao_padrao.copy()
            if selected_obras:
                colunas = ["CÓDIGO", "DESCRIÇÃO"] + selected_obras + ["Média"]
                df_matriz = pd.DataFrame(matriz_final)[colunas]
                renomear = {"CÓDIGO": nome_codigo, "DESCRIÇÃO": nome_descricao}
                df_matriz = df_matriz.rename(columns=renomear)
                colunas_novas = [nome_codigo, nome_descricao] + selected_obras + ["Média"]
                df_matriz = df_matriz[colunas_novas]
            else:
                colunas = ["CÓDIGO", "DESCRIÇÃO"]
                df_matriz = pd.DataFrame(matriz_final)[colunas]
                renomear = {"CÓDIGO": nome_codigo, "DESCRIÇÃO": nome_descricao}
                df_matriz = df_matriz.rename(columns=renomear)
                colunas_novas = [nome_codigo, nome_descricao]
                df_matriz = df_matriz[colunas_novas]
            for obra in (selected_obras if selected_obras else []):
                df_matriz[obra] = df_matriz[obra].astype(str)
            if "Média" in df_matriz.columns:
                df_matriz["Média"] = df_matriz["Média"].astype(str)
            column_config = {
                "Selecionar": st.column_config.CheckboxColumn(label="Selecionar", width="small"),
                nome_codigo: st.column_config.TextColumn(label=nome_codigo, width="small"),
                nome_descricao: st.column_config.TextColumn(label=nome_descricao, width="medium")
            }
            if selected_obras:
                for obra in selected_obras:
                    column_config[obra] = st.column_config.TextColumn(label=obra, width="small")
            if "Média" in df_matriz.columns:
                column_config["Média"] = st.column_config.TextColumn(label="Média", width="small")
            df_matriz_exibir = df_matriz.copy()
            selecao_linhas = st.session_state['selecao_linhas']
            idx_checkbox = [i for i in range(len(df_matriz_exibir)) if not (
                (i == 0 and str(df_matriz_exibir.iloc[i,1]).strip().upper() == "ÁREA M²") or
                (i == 1 and str(df_matriz_exibir.iloc[i,1]).strip().upper() == "DATA BASE")
            )]
            selecao_col = [None]*len(df_matriz_exibir)
            for idx in idx_checkbox:
                selecao_col[idx] = selecao_linhas[idx]
            df_matriz_exibir.insert(0, "Selecionar", selecao_col)
            df_matriz_editada = st.data_editor(
                df_matriz_exibir,
                use_container_width=True,
                column_config=column_config,
                disabled=[col for col in df_matriz_exibir.columns if col != "Selecionar"]
            )
            
            # Atualizar df_matriz_exibir com os dados editados
            df_matriz_exibir = df_matriz_editada.copy()
            
            if "Selecionar" in df_matriz_editada.columns:
                nova_selecao = st.session_state['selecao_linhas'][:]
                for idx in idx_checkbox:
                    nova_selecao[idx] = bool(df_matriz_editada.loc[idx, "Selecionar"])
                if len(nova_selecao) > 1:
                    nova_selecao[0] = True
                    nova_selecao[1] = True
                st.session_state['selecao_linhas'] = nova_selecao
            buffer = io.BytesIO()
            df_matriz.to_excel(buffer, index=False, engine='openpyxl')
            dados_bytes = buffer.getvalue()
            def salvar_eap_na_area_de_trabalho():
                try:
                    user_home = os.path.expanduser('~')
                    onedrive_desktop = os.path.join(user_home, 'OneDrive', 'Desktop')
                    desktop = onedrive_desktop if os.path.exists(onedrive_desktop) else os.path.join(user_home, 'Desktop')
                    if not os.path.exists(desktop):
                        os.makedirs(desktop, exist_ok=True)
                    caminho_arquivo = os.path.join(desktop, "matriz_eap.xlsx")
                    with open(caminho_arquivo, "wb") as f:
                        f.write(dados_bytes)
                    st.success(f"Arquivo salvo na área de trabalho: {caminho_arquivo}")
                except Exception as e:
                    st.error(f"Erro ao salvar na área de trabalho: {e}")
            if st.button("Salvar na área de trabalho (Excel)", key="salvar-area-trabalho-eap-excel"):
                salvar_eap_na_area_de_trabalho()
            def copiar_coluna_media():
                try:
                    if "Média" in df_matriz.columns and "Selecionar" in df_matriz_exibir.columns:
                        valores_media = []
                        for idx, row in df_matriz_exibir.iterrows():
                            if idx < 2:
                                continue
                            if row["Selecionar"]:
                                val = row["Média"]
                                if val and str(val).strip() and str(val).strip() != "":
                                    valores_media.append(str(val).strip())
                        if valores_media:
                            texto_copia = "\n".join(valores_media)
                            
                            # Tentar pyperclip primeiro (ambiente local)
                            pyperclip_success = False
                            try:
                                import pyperclip
                                pyperclip.copy(texto_copia)
                                pyperclip_success = True
                            except:
                                pass
                            
                            if pyperclip_success:
                                # Comportamento igual V1 - só mensagem de sucesso
                                st.success(f"✅ Coluna Média copiada! {len(valores_media)} valores prontos para colar (Ctrl+V) em qualquer aplicativo!")
                            else:
                                # Para ambiente web - usar JavaScript para copiar
                                import streamlit.components.v1 as components
                                
                                # JavaScript para copiar automaticamente
                                copy_js = f"""
                                <script>
                                async function copyToClipboard() {{
                                    try {{
                                        const text = `{texto_copia}`;
                                        await navigator.clipboard.writeText(text);
                                        console.log('Texto copiado para clipboard via JavaScript');
                                        return true;
                                    }} catch (err) {{
                                        console.log('Erro ao copiar via JavaScript:', err);
                                        return false;
                                    }}
                                }}
                                copyToClipboard();
                                </script>
                                """
                                
                                # Executar JavaScript
                                components.html(copy_js, height=0)
                                
                                # Mostrar mensagem de sucesso igual V1
                                st.success(f"✅ Coluna Média copiada! {len(valores_media)} valores prontos para colar (Ctrl+V) em qualquer aplicativo!")
                        else:
                            st.warning("Nenhum valor marcado para copiar na coluna Média.")
                    else:
                        st.error("Coluna Média ou coluna Selecionar não encontrada.")
                except Exception as e:
                    st.error(f"Erro ao preparar coluna Média: {e}")
            if st.button("Copiar coluna Média", key="copiar-coluna-media-eap"):
                copiar_coluna_media()
        else:
            st.info("Nenhum dado encontrado na coleção EAPS.")
    except Exception as e:
        st.error(f"Erro ao processar dados da EAP: {e}")

# ====== FUNÇÃO PRINCIPAL DA APLICAÇÃO ======
def main():
    setup_page()
    render_header()
    try:
        board_name, df = get_monday_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        df = None
    if df is not None and not df.empty:
        eaps_collection = get_eaps_collection()
        projetos_collection = get_projetos_collection()
        siglas_eaps = set()
        for eap in eaps_collection.find({}):
            projeto_id = eap.get("projeto_id", None)
            if projeto_id:
                try:
                    projeto_obj_id = ObjectId(projeto_id)
                    projeto = projetos_collection.find_one({"_id": projeto_obj_id})
                except:
                    projeto = None
                if projeto:
                    sigla = projeto.get("sigla", "")
                    if sigla and str(sigla).strip():
                        siglas_eaps.add(str(sigla).strip())
        if 'Obras' in df.columns:
            df_eaps = df[df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in siglas_eaps)].copy()
        else:
            df_eaps = df.copy()
        filters = render_filters(df_eaps, siglas_eaps)
    else:
        st.info("Nenhum dado encontrado. Verifique a conexão com o Monday.com.")
        filters = {'obras': []}
    filtered_df, _ = apply_filters(df_eaps, filters, siglas_eaps)
    obras_filtradas = filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla")).unique().tolist()
    # Passe area_simulada_val dos filtros:
    render_eap_section(obras_filtradas, filters.get('area_simulada_val'))

if __name__ == "__main__":
    main()