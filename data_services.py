"""
Módulo de serviços de dados para integração com MongoDB e Monday.com
"""

import streamlit as st
import pandas as pd
import requests
import os
import re
from typing import Tuple, Optional
from bson import ObjectId
from config_utils import APIConfig, get_eaps_collection, get_projetos_collection, clean_and_format

@st.cache_data(ttl=300, show_spinner=False)
def get_monday_data() -> Tuple[Optional[str], Optional[pd.DataFrame]]:
    """Busca dados do Monday.com e retorna DataFrame processado"""
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
        mapped_df = _process_monday_dataframe(df)
        
        return board_name, mapped_df
        
    except Exception as e:
        st.error(f"Erro ao conectar com Monday.com: {e}")
        return None, None

def _process_monday_dataframe(df):
    """Processa e mapeia o DataFrame do Monday.com"""
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
    
    mapped_df['Data'] = _extract_timeline_data(df)
    
    if 'Area' in mapped_df.columns:
        mapped_df['Area_Numeric'] = mapped_df['Area'].apply(_convert_area)
        mapped_df['Area_Display'] = mapped_df['Area']
        
    return mapped_df

def _extract_timeline_data(df):
    """Extrai dados de timeline do DataFrame"""
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
            return df[col].apply(extrair_data_inicio)
    return ''

def _convert_area(area_str):
    """Converte string de área para float"""
    if not area_str or pd.isna(area_str):
        return 0.0
    try:
        return float(str(area_str).replace('.', '').replace(',', '.'))
    except:
        return 0.0

def get_eap_data():
    """Busca dados de EAP e projetos do MongoDB"""
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
        
        projeto_info = {"sigla": sigla, "nome": nome}
        projetos_dados[str(p["_id"])] = projeto_info
        projetos_dados[p["_id"]] = projeto_info
        
    return eaps_dados, projetos_dados

def load_incc_data():
    """Carrega dados do INCC do arquivo CSV"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    incc_path = os.path.join(script_dir, 'dados_dia01_indice.csv')
    
    try:
        incc_df = pd.read_csv(
            incc_path, 
            sep=',', 
            decimal='.', 
            encoding='utf-8', 
            parse_dates=['data'], 
            dayfirst=True
        )
        incc_df = incc_df.sort_values('data')
        incc_df = incc_df[pd.to_numeric(incc_df['indice'], errors='coerce').notnull()]
        return incc_df
    except:
        return None

def get_projeto_info_by_id(projeto_id, projetos_dados):
    """Busca informações do projeto por ID com múltiplas estratégias"""
    projeto_info = projetos_dados.get(projeto_id)
    
    if not projeto_info:
        projeto_info = projetos_dados.get(str(projeto_id)) if projeto_id else None
        
    if not projeto_info and projeto_id:
        try:
            if isinstance(projeto_id, str):
                projeto_info = projetos_dados.get(ObjectId(projeto_id))
            elif isinstance(projeto_id, ObjectId):
                projeto_info = projetos_dados.get(str(projeto_id))
        except:
            pass
    
    if not projeto_info:
        projeto_info = {"sigla": "", "nome": "Obra não encontrada"}
        
    return projeto_info

def get_siglas_eaps():
    """Obtém todas as siglas de EAPs do banco"""
    eaps_collection = get_eaps_collection()
    projetos_collection = get_projetos_collection()
    
    siglas_eaps = set()
    for eap in eaps_collection.find({}):
        projeto_id = eap.get("projeto_id", None)
        if projeto_id:
            projeto = None
            
            try:
                if isinstance(projeto_id, str):
                    projeto_obj_id = ObjectId(projeto_id)
                    projeto = projetos_collection.find_one({"_id": projeto_obj_id})
                elif isinstance(projeto_id, ObjectId):
                    projeto = projetos_collection.find_one({"_id": projeto_id})
            except:
                pass
            
            if not projeto and projeto_id:
                try:
                    projeto = projetos_collection.find_one({"_id": projeto_id})
                except:
                    try:
                        projeto = projetos_collection.find_one({"_id": str(projeto_id)})
                    except:
                        pass
                        
            if projeto:
                sigla = projeto.get("sigla", "")
                if sigla and str(sigla).strip():
                    siglas_eaps.add(str(sigla).strip())
                    
    return siglas_eaps
