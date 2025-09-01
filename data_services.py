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
import tempfile
import time
import datetime
import csv
import traceback

@st.cache_data(ttl=7200, show_spinner=False)
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

@st.cache_data(ttl=86400, show_spinner=False)
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

@st.cache_data(ttl=86400, show_spinner=False)
def load_incc_data():
    """Carrega dados do INCC do arquivo CSV"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    incc_path = os.path.join(script_dir, 'dados_dia01_indice.csv')

    def _collect_incc_csv(final_path):
        """Coleta dados do site e escreve CSV no mesmo formato, usando arquivo temporário e replace atômico."""
        url = "https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59"
        meses = {
            'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 
            'MAI': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08', 
            'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
        }

        try:
            import requests
            from bs4 import BeautifulSoup
        except Exception:
            raise

        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'html.parser')

            dados = []
            tables = soup.find_all('table')
            ano_atual = None
            for table in tables:
                # tenta extrair ano
                txt = table.get_text(separator=' ')
                m = re.search(r'Ano:\s*(\d{4})', txt)
                if m:
                    ano_atual = m.group(1)
                    continue

                linhas = table.find_all('tr')
                for linha in linhas:
                    cols = linha.find_all('td')
                    if len(cols) >= 2 and ano_atual:
                        mes = cols[0].get_text(strip=True).upper()
                        indice = cols[1].get_text(strip=True).replace('.', '').replace(',', '.')
                        if mes in meses:
                            data = f"01/{meses[mes]}/{ano_atual}"
                            try:
                                valor = float(indice)
                                dados.append([data, valor])
                            except:
                                continue

            if not dados:
                raise RuntimeError('Nenhum dado coletado do site INCC')

            # escrever em arquivo temporário e mover atômico
            tmp_fd, tmp_path = tempfile.mkstemp(prefix='incc_', suffix='.csv', dir=script_dir)
            os.close(tmp_fd)
            try:
                with open(tmp_path, 'w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.writer(f)
                    writer.writerow(['data', 'indice'])
                    writer.writerows(dados)
                os.replace(tmp_path, final_path)
            finally:
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except:
                        pass

        except Exception as e:
            # propaga exceção para o chamador tratar (fallback)
            raise

    def _is_csv_outdated(path):
        try:
            df_check = pd.read_csv(path, usecols=['data'], parse_dates=['data'], dayfirst=True, encoding='utf-8-sig')
            if df_check.empty:
                return True
            max_date = df_check['data'].max()
            if pd.isna(max_date):
                return True
            today = datetime.date.today()
            first_of_month = datetime.date(today.year, today.month, 1)
            return max_date.date() < first_of_month
        except Exception:
            return True

    # Lock handling to avoid múltiplos processos baixando simultaneamente
    lock_path = incc_path + '.lock'
    try:
        # se arquivo não existe ou está desatualizado, coletar
        need_collect = False
        if not os.path.exists(incc_path):
            need_collect = True
        else:
            if _is_csv_outdated(incc_path):
                need_collect = True

        if need_collect:
            # tentar criar lock atômico
            got_lock = False
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                os.write(fd, str(os.getpid()).encode())
                os.close(fd)
                got_lock = True
            except FileExistsError:
                got_lock = False

            if got_lock:
                try:
                    _collect_incc_csv(incc_path)
                except Exception:
                    # falha na coleta: se existir CSV antigo, seguimos com ele; caso contrário, repropaga
                    if not os.path.exists(incc_path):
                        raise
                finally:
                    try:
                        os.remove(lock_path)
                    except:
                        pass
            else:
                # outro processo está coletando: aguardar até 10s pelo arquivo ou timeout
                waited = 0.0
                while waited < 10.0:
                    if os.path.exists(incc_path):
                        break
                    time.sleep(0.25)
                    waited += 0.25

        # se chegamos aqui e arquivo existe, carregar via função cacheada por mtime
        if os.path.exists(incc_path):
            mtime = os.path.getmtime(incc_path)
            return _load_incc_data_cached(mtime, incc_path)

        return None
    except Exception:
        # em caso de erro final, não quebrar app
        return None


@st.cache_data(ttl=86400, show_spinner=False)
def _load_incc_data_cached(mtime, path):
    """Leitura cacheada do CSV; a chave do cache inclui o mtime para invalidar quando o arquivo mudar."""
    try:
        incc_df = pd.read_csv(
            path,
            sep=',',
            decimal='.',
            encoding='utf-8-sig',
            parse_dates=['data'],
            dayfirst=True
        )
        incc_df = incc_df.sort_values('data')
        incc_df = incc_df[pd.to_numeric(incc_df['indice'], errors='coerce').notnull()]
        return incc_df
    except Exception:
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

@st.cache_data(ttl=86400, show_spinner=False)
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
