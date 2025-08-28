"""
Script para coleta de dados do INCC (Índice Nacional da Construção Civil)
Extrai dados do site do Secovi e gera arquivo CSV
"""

import requests
from bs4 import BeautifulSoup
import csv
import re

def extrair_ano(table):
    """Extrai ano do cabeçalho da tabela"""
    ano_match = re.search(r"Ano: (\d{4})", table.text)
    if ano_match:
        return ano_match.group(1)
    return None

def coletar_dados_incc():
    """Coleta dados do INCC do site do Secovi"""
    url = "https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    
    meses = {
        'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 
        'MAI': '05', 'JUN': '06', 'JUL': '07', 'AGO': '08', 
        'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
    }
    
    dados = []
    tables = soup.find_all("table")
    ano_atual = None
    
    for table in tables:
        ano = extrair_ano(table)
        if ano:
            ano_atual = ano
            continue
            
        linhas = table.find_all("tr")
        for linha in linhas:
            colunas = linha.find_all("td")
            if len(colunas) >= 2 and ano_atual:
                mes = colunas[0].get_text(strip=True)
                indice = colunas[1].get_text(strip=True).replace('.', '').replace(',', '.')
                
                if mes in meses:
                    data = f"01/{meses[mes]}/{ano_atual}"
                    try:
                        valor = float(indice)
                        dados.append([data, valor])
                    except ValueError:
                        pass
    
    with open("dados_dia01_indice.csv", "w", newline='', encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["data", "indice"])
        writer.writerows(dados)
    
    print("Arquivo dados_dia01_indice.csv gerado com sucesso!")

if __name__ == "__main__":
    coletar_dados_incc()
