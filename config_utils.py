"""
Módulo de configurações e utilitários para o sistema TOOLS Calculator
"""

import streamlit as st
import pandas as pd
import json
import re
import os
from datetime import datetime
from dateutil.relativedelta import relativedelta
from typing import Tuple, Optional
from pymongo import MongoClient

# Configuração segura de credenciais
def get_credentials():
    """
    Obtém credenciais de forma segura usando abordagem híbrida:
    1. Tenta st.secrets (Streamlit Cloud)
    2. Tenta variáveis de ambiente (.env ou sistema)
    3. Fallback para valores padrão (apenas para desenvolvimento)
    """
    try:
        # Tentativa 1: Streamlit Secrets (recomendado para Streamlit Cloud)
        mongo_uri = st.secrets["MONGO_URI"]
        api_key = st.secrets["monday"]["API_KEY"]
        board_id = st.secrets["monday"]["BOARD_ID"]
        return mongo_uri, api_key, board_id
    except (KeyError, AttributeError, FileNotFoundError):
        pass
    
    try:
        # Tentativa 2: Variáveis de ambiente
        mongo_uri = os.getenv("MONGO_URI")
        api_key = os.getenv("MONDAY_API_KEY")
        board_id = int(os.getenv("MONDAY_BOARD_ID", "926240878"))
        
        if mongo_uri and api_key:
            return mongo_uri, api_key, board_id
    except (ValueError, TypeError):
        pass
    
    # Fallback: Avisar que credenciais não foram encontradas
    st.error("🚨 Credenciais não encontradas! Configure st.secrets ou variáveis de ambiente.")
    st.stop()

# Obter credenciais seguras
MONGO_URI, API_KEY_VALUE, BOARD_ID_VALUE = get_credentials()

class APIConfig:
    """Configurações da API do Monday.com"""
    API_KEY = API_KEY_VALUE
    BASE_URL = 'https://api.monday.com/v2'
    BOARD_ID = BOARD_ID_VALUE

@st.cache_resource
def get_mongo_client():
    """Retorna cliente MongoDB com cache"""
    return MongoClient(MONGO_URI)

def get_projetos_collection():
    """Retorna coleção de projetos"""
    return get_mongo_client()['ToolsConnect']['projetos']

def get_eaps_collection():
    """Retorna coleção de EAPs"""
    return get_mongo_client()['ToolsConnect']['eaps']

def clean_and_format(val, tipo="str"):
    """Função utilitária para limpeza e formatação de dados"""
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
    """Formata índice INCC"""
    if val is None:
        return '—'
    try:
        val_num = float(val.replace('.', '').replace(',', '.')) if isinstance(val, str) else float(val)
        return f"{round(val_num, 2):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return str(val)

def format_area_total(val):
    """Formata área total"""
    if val is None or not isinstance(val, (int, float)):
        return '—'
    return f"{int(round(val)):,}".replace(",", ".")

def calcular_valor_m2(custo, area, data_base, incc_df):
    """Calcula valor por m² ajustado pelo INCC"""
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

def setup_page():
    """Configuração da página Streamlit"""
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
        .header-container {{ background: white; padding: 1.5rem 2rem; border-bottom: 1px solid #e5e7eb; margin-bottom: 2rem; display: flex; justify-content: space-between; align-items: center; }}
        .tools-title {{ color: #0e938e; font-size: 3rem; font-weight: 700; letter-spacing: -2px; margin: 0; font-family: "Source Sans 3", sans-serif; }}
        .tabs-container {{ border-bottom: 2px solid #0e938e; margin-bottom: 2rem; padding-left: 2rem; }}
        .tab-active {{ display: inline-block; padding: 0.75rem 0; margin-right: 3rem; color: #0e938e; font-weight: 600; font-size: 0.875rem; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 3px solid #0e938e; font-family: "Source Sans 3", sans-serif; }}
        .filters-section {{ padding: 0 2rem; margin-bottom: 1.5rem; }}
        .filter-label {{ color: #6b7280; font-size: 0.75rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.25rem; font-family: "Source Sans 3", sans-serif; }}
        .stTextInput > div > div > input {{ border: 1px solid #d1d5db !important; border-radius: 6px !important; background: white !important; font-size: 0.875rem !important; padding: 0.5rem 0.75rem !important; font-family: "Source Sans 3", sans-serif !important; color: #374151 !important; }}
        .stMultiSelect > div > div {{ border: 1px solid #d1d5db !important; border-radius: 6px !important; font-family: "Source Sans 3", sans-serif !important; background: #f9fafb !important; }}
        .stSlider > div > div > div > div {{ background-color: #0e938e !important; }}
        #MainMenu {{visibility: hidden;}} footer {{visibility: hidden;}} header {{visibility: hidden;}} .stDeployButton {{visibility: hidden;}}
    </style>
    """, unsafe_allow_html=True)

def render_header():
    """Renderiza o cabeçalho da página"""
    st.markdown(
        '''<div class="header-container"><div class="tools-title">TOOLS</div></div><div class="tabs-container"><span class="tab-active">TLS-001 RECURSOS E TIMELINE DO PROJETO</span></div>''',
        unsafe_allow_html=True
    )
