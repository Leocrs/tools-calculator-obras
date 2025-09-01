"""
Módulo principal da interface do usuário - TOOLS Calculator
"""

import streamlit as st
import pandas as pd
import io
import re
from config_utils import (
    setup_page, render_header, clean_and_format, 
    calcular_valor_m2, format_indice_incc, format_area_total
)
from data_services import (
    get_monday_data, get_eap_data, load_incc_data,
    get_projeto_info_by_id, get_siglas_eaps
)

def create_multiselect_filter(label, options_base, key):
    """Cria filtro multiselect com comportamento customizado"""
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
    
    if key == "obras" and not st.session_state[key]:
        return options_base
    return st.session_state[key]

def render_filters(df_eaps, siglas_eaps):
    """Renderiza os filtros principais da interface"""
    st.markdown('<div class="filters-section">', unsafe_allow_html=True)
    
    if "modo_filtro" not in st.session_state:
        st.session_state["modo_filtro"] = "Qualquer critério (OU/União)"
        
    filtro_modo = st.radio(
        "Modo de combinação dos filtros:",
        ["Todos os critérios (E/Interseção)", "Qualquer critério (OU/União)"],
        horizontal=True,
        key="modo_filtro"
    )
    
    obras_filter = st.session_state.get("obras", [])
    construtora_filter = st.session_state.get("construtora", [])
    arquitetura_filter = st.session_state.get("arquitetura", [])
    local_filter = st.session_state.get("local", "")
    
    df_filtrado = df_eaps.copy()
    if obras_filter:
        df_filtrado = df_filtrado[df_filtrado['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in obras_filter)]
    if construtora_filter:
        df_filtrado = df_filtrado[df_filtrado['Construtora'].astype(str).str.strip().str.lower().isin([str(x).strip().lower() for x in construtora_filter])]
    if arquitetura_filter:
        df_filtrado = df_filtrado[df_filtrado['Arquitetura'].astype(str).str.strip().str.lower().isin([str(x).strip().lower() for x in arquitetura_filter])]
    if local_filter:
        df_filtrado = df_filtrado[df_filtrado['Local'].astype(str).str.strip().str.lower() == str(local_filter).strip().lower()]
    
    obras_opcoes = sorted(df_eaps['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla")).unique().tolist())
    construtora_opcoes = sorted([x for x in df_eaps['Construtora'].dropna().astype(str).str.strip().unique().tolist() if x])
    arquitetura_opcoes = sorted(df_eaps['Arquitetura'].dropna().astype(str).str.strip().unique().tolist())
    locais_opcoes = sorted(df_eaps['Local'].dropna().astype(str).str.strip().unique().tolist())
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
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

def apply_filters(df_eaps, filters, siglas_eaps):
    """Aplica os filtros no DataFrame"""
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
    
    if filters['obras'] is not None and len(filters['obras']) == 0 and 'Obras' in df_eaps.columns:
        return filtered_df.iloc[0:0], True
    
    if filters['modo'] == "Todos os critérios (E/Interseção)":
        # Aplicar filtro de obras com OR dentro do grupo (múltiplas obras permitidas)
        if filters['obras'] and len(filters['obras']) > 0 and 'Obras' in df_eaps.columns:
            filtered_df = filtered_df[filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in filters['obras'])]
            filtro_aplicado = True
            
        # Aplicar filtros de construtora e arquitetura com OR dentro de cada grupo
        for filter_key, column in [('construtora', 'Construtora'), ('arquitetura', 'Arquitetura')]:
            if filters[filter_key] and len(filters[filter_key]) > 0 and column in df_eaps.columns:
                selected = [str(x).strip().lower() for x in filters[filter_key]]
                filtered_df = filtered_df[
                    filtered_df[column].astype(str).str.strip().str.lower().isin(selected)
                ]
                filtro_aplicado = True
    else:
        # Modo "Qualquer critério (OU/União)" - une os índices de todos os filtros aplicados
        indices = set()
        
        # Filtro de obras
        if filters['obras'] and len(filters['obras']) > 0 and 'Obras' in df_eaps.columns:
            indices_obras = set(filtered_df[filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in filters['obras'])].index)
            indices.update(indices_obras)
            
        # Filtros de construtora e arquitetura
        for filter_key, column in [('construtora', 'Construtora'), ('arquitetura', 'Arquitetura')]:
            if filters[filter_key] and len(filters[filter_key]) > 0 and column in df_eaps.columns:
                selected = [str(x).strip().lower() for x in filters[filter_key]]
                mask = filtered_df[column].astype(str).str.strip().str.lower().isin(selected)
                indices.update(set(filtered_df[mask].index))
                
        # Aplicar união de todos os índices encontrados
        if indices:
            filtered_df = filtered_df.loc[list(indices)]
            filtro_aplicado = True
            
    return filtered_df, filtro_aplicado

@st.cache_data(ttl=180, show_spinner=True)
def process_eap_matrix(_eaps_dados, _projetos_dados, selected_obras, _monday_df, _incc_df_eap, area_simulada_val=None):
    """Processa a matriz EAP com cálculos INCC"""
    siglas_obras_eap = set()
    data_ref_dict = {}
    area_m2_dict_monday = {}
    
    for doc in _eaps_dados:
        projeto_id = doc.get("projeto_id")
        projeto_info = get_projeto_info_by_id(projeto_id, _projetos_dados)
        sigla_obra = projeto_info["sigla"] or projeto_info["nome"]
        siglas_obras_eap.add(sigla_obra)
        data_ref_dict[sigla_obra] = doc.get("dataBase", "")
    
    if _monday_df is not None and not _monday_df.empty:
        for idx, row in _monday_df.iterrows():
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
    
    for doc in _eaps_dados:
        projeto_id = doc.get("projeto_id")
        projeto_info = get_projeto_info_by_id(projeto_id, _projetos_dados)
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
                
                if _incc_df_eap is not None and valor and str(valor).strip() not in ['', 'nan', 'none']:
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
                            
                            valor_unitario_real = calcular_valor_m2(custo_raw, area_real, data_base_obra, _incc_df_eap)
                            
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

def render_eap_section(selected_obras, area_simulada_val=None):
    """Renderiza a seção principal EAP"""
    try:
        eaps_dados, projetos_dados = get_eap_data()
        incc_df_eap = load_incc_data()
        
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
            # Filtra para exibir apenas as linhas selecionadas (exceto cabeçalhos)
            linhas_exibir = [i for i in range(len(df_matriz_exibir)) if (i < 2 or selecao_col[i])]
            df_matriz_exibir = df_matriz_exibir.iloc[linhas_exibir].reset_index(drop=True)
            df_matriz_editada = st.data_editor(
                df_matriz_exibir,
                use_container_width=True,
                column_config=column_config,
                disabled=[col for col in df_matriz_exibir.columns if col != "Selecionar"]
            )
            if "Selecionar" in df_matriz_editada.columns:
                nova_selecao = st.session_state['selecao_linhas'][:]
                mudou = False
                for idx in idx_checkbox:
                    if idx < len(df_matriz_editada):
                        novo_valor = bool(df_matriz_editada.loc[idx, "Selecionar"])
                        if nova_selecao[idx] != novo_valor:
                            nova_selecao[idx] = novo_valor
                            mudou = True
                if len(nova_selecao) > 1:
                    nova_selecao[0] = True
                    nova_selecao[1] = True
                st.session_state['selecao_linhas'] = nova_selecao
                if mudou:
                    st.rerun()
            buffer = io.BytesIO()
            df_matriz.to_excel(buffer, index=False, engine='openpyxl')
            dados_bytes = buffer.getvalue()
            st.download_button(
                label="Baixar Excel",
                data=dados_bytes,
                file_name="relatorio_obras.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            def copiar_coluna_media():
                try:
                    if "Média" in df_matriz.columns and "Selecionar" in df_matriz_exibir.columns:
                        valores_media = []
                        for idx, row in df_matriz_exibir.iterrows():
                            if idx < 2:
                                continue
                            if row["Selecionar"]:
                                val = row["Média"]
                                if val and str(val).strip():
                                    valores_media.append(str(val).strip())
                        
                        if valores_media:
                            texto_copia = "\n".join(valores_media)
                            try:
                                import pyperclip
                                pyperclip.copy(texto_copia)
                                st.success(f"✅ Coluna Média copiada! {len(valores_media)} valores prontos para colar (Ctrl+V) em qualquer aplicativo!")
                            except:
                                import streamlit.components.v1 as components
                                components.html(f"""
                                <button onclick="navigator.clipboard.writeText(`{texto_copia}`).then(()=>document.getElementById('msg').innerHTML='✅ Copiado! Cole com Ctrl+V')" 
                                style="background:#00cc88;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold">
                                Copiar {len(valores_media)} valores</button>
                                <div id="msg" style="margin-top:10px;font-weight:bold"></div>
                                """, height=80)
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

def main():
    """Função principal da aplicação"""
    setup_page()
    render_header()
    
    try:
        board_name, df = get_monday_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        df = None
    
    if df is not None and not df.empty:
        siglas_eaps = get_siglas_eaps()
        
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
    
    render_eap_section(obras_filtradas, filters.get('area_simulada_val'))

if __name__ == "__main__":
    main()
