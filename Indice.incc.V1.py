
import requests
from bs4 import BeautifulSoup
import csv
import re

# URL do INCC no site do Secovi
url = "https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59"
response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

# Função para extrair ano do cabeçalho da tabela
def extrair_ano(table):
    ano_match = re.search(r"Ano: (\d{4})", table.text)
    if ano_match:
        return ano_match.group(1)
    return None

# Mapeamento de meses
meses = {
    'JAN': '01', 'FEV': '02', 'MAR': '03', 'ABR': '04', 'MAI': '05', 'JUN': '06',
    'JUL': '07', 'AGO': '08', 'SET': '09', 'OUT': '10', 'NOV': '11', 'DEZ': '12'
}

dados = []



# Nova lógica: associar o ano da tabela de cabeçalho à próxima tabela de dados (sem prints de debug)
tables = soup.find_all("table")
ano_atual = None
for table in tables:
    ano = extrair_ano(table)
    if ano:
        ano_atual = ano
        continue  # pula para a próxima tabela, que deve ser a de dados
    # Se não encontrou ano, tenta processar como tabela de dados
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

# Salva sobrescrevendo o arquivo oficial
with open("dados_dia01_indice.csv", "w", newline='', encoding="utf-8-sig") as f:
    writer = csv.writer(f)
    writer.writerow(["data", "indice"])
    writer.writerows(dados)

print("Arquivo dados_dia01_indice.csv gerado com sucesso! Somente dados reais do site.")
