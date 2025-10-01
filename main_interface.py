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
    if key not in st.session_state:
        st.session_state[key] = []
        
    st.multiselect(
        "", options_base, key=key,
        label_visibility="collapsed",
        placeholder="Escolha uma opção"
    )
    
    return options_base if key == "obras" and not st.session_state[key] else st.session_state[key]

def render_filters(df_eaps, siglas_eaps):
    """Renderiza os filtros principais da interface"""
    st.markdown('<div class="filters-section">', unsafe_allow_html=True)
    
    if "modo_filtro" not in st.session_state:
        st.session_state["modo_filtro"] = "Qualquer critério (OU/União)"
        
    filtro_modo = st.radio(
        "Modo de combinação dos filtros:",
        ["Todos os critérios (E/Interseção)", "Qualquer critério (OU/União)"],
        horizontal=True, key="modo_filtro"
    )
    
    # Preparação das opções
    obras_opcoes = sorted(df_eaps['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla")).unique().tolist())
    construtora_opcoes = sorted([x for x in df_eaps['Construtora'].dropna().astype(str).str.strip().unique().tolist() if x])
    arquitetura_opcoes = sorted(df_eaps['Arquitetura'].dropna().astype(str).str.strip().unique().tolist())
    locais_opcoes = sorted(df_eaps['Local'].dropna().astype(str).str.strip().unique().tolist())
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.markdown('<div class="filter-label">ÁREA (m²)</div>', unsafe_allow_html=True)
        area_range = None
        if 'Area_Numeric' in df_eaps.columns:
            valid_areas = df_eaps['Area_Numeric'].dropna()
            if not valid_areas.empty:
                min_area, max_area = 0, int(valid_areas.max())
                area_range = st.slider(
                    "", min_value=min_area, max_value=max_area, 
                    value=(min_area, max_area), step=100, 
                    key="area", label_visibility="collapsed", format="%d m²"
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
            "", value="", placeholder="Digite uma área para simulação (opcional)",
            key="area_simulada", label_visibility="collapsed"
        )
        
        area_simulada_val = None
        if area_simulada:
            try:
                area_simulada_val = float(str(area_simulada).replace('.', '').replace(',', '.'))
            except:
                st.warning("Área simulada inválida. Use apenas números.")
            
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

    if filters.get('modo') == "Qualquer critério (OU/União)":
        indices_finais = set()

        # Filtro de construtora por substring
        if filters.get('construtora') and 'Construtora' in filtered_df.columns:
            mask = filtered_df['Construtora'].astype(str).apply(
                lambda val: any(str(f).strip().lower() in val.strip().lower() 
                              for f in filters['construtora'])
            )
            indices_finais.update(filtered_df[mask].index)

        # Filtro de arquitetura por substring
        if filters.get('arquitetura') and 'Arquitetura' in filtered_df.columns:
            mask = filtered_df['Arquitetura'].astype(str).apply(
                lambda val: any(str(f).strip().lower() in val.strip().lower() 
                              for f in filters['arquitetura'])
            )
            indices_finais.update(filtered_df[mask].index)

        # Se não há filtros aplicados, retorna todas as obras
        if not indices_finais:
            tem_filtros = ((filters.get('construtora') and len(filters['construtora']) > 0) or
                          (filters.get('arquitetura') and len(filters['arquitetura']) > 0))
            
            if tem_filtros:
                filtered_df = filtered_df.iloc[0:0]  # Retorna vazio se tem filtros mas sem resultado
        else:
            filtered_df = filtered_df.loc[list(indices_finais)]

    else:
        # Modo AND
        if filters.get('construtora') and 'Construtora' in filtered_df.columns:
            mask = filtered_df['Construtora'].astype(str).apply(
                lambda val: any(str(f).strip().lower() in val.strip().lower() 
                              for f in filters['construtora'])
            )
            filtered_df = filtered_df[mask]

        if filters.get('arquitetura') and 'Arquitetura' in filtered_df.columns:
            mask = filtered_df['Arquitetura'].astype(str).apply(
                lambda val: any(str(f).strip().lower() in val.strip().lower() 
                              for f in filters['arquitetura'])
            )
            filtered_df = filtered_df[mask]

        if filters.get('obras') and len(filters['obras']) > 0 and 'Obras' in filtered_df.columns:
            filtered_df = filtered_df[filtered_df['Obras'].apply(
                lambda x: clean_and_format(x, tipo="sigla") in filters['obras'])]

        if 'Area_Numeric' in filtered_df.columns and filters.get('area_range'):
            filtered_df = filtered_df[
                (filtered_df['Area_Numeric'] >= filters['area_range'][0]) & 
                (filtered_df['Area_Numeric'] <= filters['area_range'][1])
            ]

        if filters.get('local'):
            filtered_df = filtered_df[filtered_df['Local'].str.contains(
                filters['local'], case=False, na=False)]

    return filtered_df, True

@st.cache_data(ttl=180, show_spinner=True)
def process_eap_matrix(_eaps_dados, _projetos_dados, selected_obras, _monday_df, _incc_df_eap, area_simulada_val=None):
    """Processa a matriz EAP com cálculos INCC"""
    siglas_obras_eap = set()
    data_ref_dict = {}
    area_m2_dict_monday = {}
    
    # Processa dados dos projetos
    for doc in _eaps_dados:
        projeto_id = doc.get("projeto_id")
        projeto_info = get_projeto_info_by_id(projeto_id, _projetos_dados)
        sigla_obra = projeto_info["sigla"] or projeto_info["nome"]
        siglas_obras_eap.add(sigla_obra)
        data_ref_dict[sigla_obra] = doc.get("dataBase", "")
    
    # Processa áreas do Monday
    if _monday_df is not None and not _monday_df.empty:
        for idx, row in _monday_df.iterrows():
            nome_obra = str(row['Obras']).strip()
            area_obra = str(row['Area']).strip() if 'Area' in row else ''
            if nome_obra:
                area_m2_dict_monday[nome_obra] = area_obra
    
    matriz_final = []
    
    # Linha de área
    area_row = {"CÓDIGO": "", "DESCRIÇÃO": "ÁREA M²"}
    if selected_obras:
        for obra in selected_obras:
            area_val = area_m2_dict_monday.get(obra)
            if not area_val or str(area_val).strip().lower() in ["", "nan", "none"]:
                for nome_monday, area_monday in area_m2_dict_monday.items():
                    if obra.lower() in nome_monday.lower():
                        area_val = area_monday
                        break
            area_row[obra] = clean_and_format(area_val, tipo="area") if area_val else ""
        area_row["Média"] = ""
    matriz_final.append(area_row)
    
    # Linha de data base
    dataref_row = {"CÓDIGO": "", "DESCRIÇÃO": "DATA BASE"}
    if selected_obras:
        for sigla in selected_obras:
            dataref_row[sigla] = str(data_ref_dict.get(sigla, ""))
        dataref_row["Média"] = ""
    matriz_final.append(dataref_row)
    
    # Processa itens EAP
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
    
    # Gera linhas da matriz
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
                
                # Aplica INCC se disponível
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
                                area_real = float(str(area_obra_str).replace('.', '').replace(',', '.')) if area_obra_str and str(area_obra_str).strip() else 1.0
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
        eaps_dados, projetos_dados = get_eap_data(filter_version=9)
        incc_df_eap = load_incc_data()
        
        if eaps_dados:
            board_name, monday_df = get_monday_data()
            matriz_final = process_eap_matrix(
                eaps_dados, projetos_dados, selected_obras, monday_df, incc_df_eap, area_simulada_val
            )
            
            nome_codigo, nome_descricao = "Código", "Descrição"
            
            if 'selecao_linhas' not in st.session_state or len(st.session_state['selecao_linhas']) != len(matriz_final):
                st.session_state['selecao_linhas'] = [True] * len(matriz_final)
            
            # Configura DataFrame
            if selected_obras:
                colunas = ["CÓDIGO", "DESCRIÇÃO"] + selected_obras + ["Média"]
                df_matriz = pd.DataFrame(matriz_final)[colunas]
                df_matriz = df_matriz.rename(columns={"CÓDIGO": nome_codigo, "DESCRIÇÃO": nome_descricao})
                colunas_novas = [nome_codigo, nome_descricao] + selected_obras + ["Média"]
                df_matriz = df_matriz[colunas_novas]
            else:
                colunas = ["CÓDIGO", "DESCRIÇÃO"]
                df_matriz = pd.DataFrame(matriz_final)[colunas]
                df_matriz = df_matriz.rename(columns={"CÓDIGO": nome_codigo, "DESCRIÇÃO": nome_descricao})
                
            # Converte para string
            for obra in (selected_obras if selected_obras else []):
                df_matriz[obra] = df_matriz[obra].astype(str)
                
            if "Média" in df_matriz.columns:
                df_matriz["Média"] = df_matriz["Média"].astype(str)
            
            # Configuração das colunas
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
            
            # Preparação para exibição
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
            
            # Filtra linhas selecionadas
            linhas_exibir = [i for i in range(len(df_matriz_exibir)) if (i < 2 or selecao_col[i])]
            df_matriz_exibir = df_matriz_exibir.iloc[linhas_exibir].reset_index(drop=True)
            
            df_matriz_editada = st.data_editor(
                df_matriz_exibir,
                use_container_width=True,
                column_config=column_config,
                disabled=[col for col in df_matriz_exibir.columns if col != "Selecionar"]
            )
            
            # Atualiza seleção
            if "Selecionar" in df_matriz_editada.columns:
                nova_selecao = st.session_state['selecao_linhas'][:]
                mudou = False
                
                # Mapeia os índices do dataframe editado para os índices originais
                for i, linha_original_idx in enumerate(linhas_exibir):
                    if i < len(df_matriz_editada) and linha_original_idx in idx_checkbox:
                        novo_valor = bool(df_matriz_editada.loc[i, "Selecionar"])
                        if nova_selecao[linha_original_idx] != novo_valor:
                            nova_selecao[linha_original_idx] = novo_valor
                            mudou = True
                
                # Garante que as linhas de cabeçalho permaneçam sempre selecionadas
                if len(nova_selecao) > 1:
                    nova_selecao[0] = True
                    nova_selecao[1] = True
                    
                st.session_state['selecao_linhas'] = nova_selecao
                if mudou:
                    st.rerun()
            
            # Download Excel
            buffer = io.BytesIO()
            df_matriz.to_excel(buffer, index=False, engine='openpyxl')
            dados_bytes = buffer.getvalue()
            st.download_button(
                label="Baixar Excel",
                data=dados_bytes,
                file_name="relatorio_obras.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Botão de cópia
            from st_copy import copy_button
            valores_media = []
            if "Média" in df_matriz.columns and "Selecionar" in df_matriz_exibir.columns:
                for idx, row in df_matriz_exibir.iterrows():
                    if idx >= 2 and row["Selecionar"]:
                        val = row["Média"]
                        if val and str(val).strip():
                            valores_media.append(str(val).strip())
            
            texto_copia = "\n".join(valores_media) if valores_media else ""
            col1, col2 = st.columns([0.1, 1])
            with col1:
                st.write('Coluna Média')
            with col2:
                copy_button(
                    texto_copia,
                    icon='material_symbols',
                    tooltip='Copiar valores da coluna Média',
                    copied_label='Valores copiados!',
                    key='copiar-coluna-media-eap',
                )
                
        else:
            st.info("Nenhum dado encontrado na coleção EAPS.")
            
    except Exception as e:
        st.error(f"Erro ao processar dados da EAP: {e}")

def main():
    """Função principal da aplicação"""
    setup_page()
    render_header()
    
    # Inicializar variáveis para evitar UnboundLocalError
    df_eaps = pd.DataFrame()
    siglas_eaps = []
    
    try:
        board_name, df = get_monday_data()
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        df = None
    
    if df is not None and not df.empty:
        siglas_eaps = get_siglas_eaps()
        
        df_eaps = df[df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla") in siglas_eaps)].copy() if 'Obras' in df.columns else df.copy()
            
        filters = render_filters(df_eaps, siglas_eaps)
    else:
        st.error("🚨 Nenhum dado encontrado. Verifique a conexão com o Monday.com.")
        st.info("💡 Verifique se suas credenciais estão corretas em .streamlit/secrets.toml")
        filters = {'obras': []}
        # Retornar early para evitar processamento adicional quando não há dados
        return
    
    filtered_df, _ = apply_filters(df_eaps, filters, siglas_eaps)
    if 'Obras' in filtered_df.columns:
        todas_obras_filtradas = filtered_df['Obras'].apply(lambda x: clean_and_format(x, tipo="sigla")).unique().tolist()
        if filters.get('obras') and len(filters['obras']) > 0:
            obras_filtradas = [obra for obra in todas_obras_filtradas if obra in filters['obras']]
        else:
            obras_filtradas = todas_obras_filtradas
    else:
        obras_filtradas = []
    
    render_eap_section(obras_filtradas, filters.get('area_simulada_val'))

if __name__ == "__main__":
    main()
