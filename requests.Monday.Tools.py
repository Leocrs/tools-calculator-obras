import requests
import pandas as pd
import re

def get_dataMonday(board):
    api = 'eyJhbGciOiJIUzI1NiJ9.eyJ0aWQiOjI2Njg4NzkwNiwiYWFpIjoxMSwidWlkIjoyMzA5NjM0MiwiaWFkIjoiMjAyMy0wNy0wNVQxNDoyNTo1NS4wMDBaIiwicGVyIjoibWU6d3JpdGUiLCJhY3RpZCI6NDkwNjU3MCwicmduIjoidXNlMSJ9.tRWcVx3Q9oUEPKRMdaEiFzqCf1n0F7NelbjY09jQix4'
    url = 'https://api.monday.com/v2'
    query = '''
    query {
      boards(ids: %s) {
        items_page (limit:500) {
          items {
            id
            name
            column_values(ids: ["status6", "dup__of_equipe", "produto", "timeline", "location", "dup__of_produto"]) {
              id
              text
            }
          }
        }
      }
    }
    ''' % board

    headers = {
        'Authorization': api
    }
    response = requests.post(url, json={'query': query}, headers=headers)
    return transformar_dados(response.json())

def extrair_estado(local):
    """
    Extrai o estado da coluna LOCAL
    """
    if not local or pd.isna(local):
        return "N/A"
    
    # Padrões para extrair estado
    padroes = [
        r'- ([A-Z]{2}), Brasil',           # "São Paulo - SP, Brasil"
        r'- ([A-Z]{2}, Brasil)',          # "São Paulo - SP, Brasil" (variação)
        r'/([A-Z]{2})\b',                 # "Itupeva /SP"
        r'- ([A-Z]{2}),',                 # "São Paulo - SP,"
        r'State of ([A-Za-z\s]+), Brazil', # "State of São Paulo, Brazil"
        r', ([A-Z]{2}) \d',               # ", SP 04523-010"
        r'([A-Z]{2}), Brasil'             # "SP, Brasil"
    ]
    
    for padrao in padroes:
        match = re.search(padrao, local)
        if match:
            estado = match.group(1)
            # Mapear nomes completos para siglas
            mapeamento_estados = {
                'São Paulo': 'SP',
                'Alagoas': 'AL',
                'Rio de Janeiro': 'RJ',
                'Santa Catarina': 'SC',
                'Minas Gerais': 'MG'
            }
            return mapeamento_estados.get(estado, estado)
    
    return "N/A"

def transformar_dados(input_data):
    try:
        items = input_data['data']['boards'][0]['items_page']['items']
    except (KeyError, IndexError):
        raise ValueError("Formato de dados de entrada inválido.")

    resultado = []

    for item in items:
        local = next((c['text'] for c in item.get('column_values', []) if c['id'] == 'location'), '')
        
        novo_item = {
            "ID": item.get('id', ''),  # Adicionado Item ID
            "SIGLA": item.get('name', '').split('-')[0],
            "OBRA": item.get('name', ''),
            "INICIO": next(
                (c['text'].split(' - ')[0] for c in item.get('column_values', []) 
                if c['id'] == 'timeline' and 'text' in c and ' - ' in c['text']), 
                None
            ),
            "TERMINO": next(
                (c['text'].split(' - ')[1] for c in item.get('column_values', []) 
                if c['id'] == 'timeline' and 'text' in c and ' - ' in c['text']), 
                None
            ),
            "FASE": next((c['text'] for c in item.get('column_values', []) if c['id'] == 'status6'), ''),
            "RCR": next((c['text'].split('@')[0].replace('.',' ').upper() for c in item.get('column_values', []) if c['id'] == 'dup__of_equipe'), ''),
            "PRODUTO": next((c['text'] for c in item.get('column_values', []) if c['id'] == 'produto'), ''),
            "LOCAL": local,
            "ESTADO": extrair_estado(local),  # Nova coluna ESTADO
            "CLIENTE": next((c['text'] for c in item.get('column_values', []) if c['id'] == 'dup__of_produto'), ''),
        }
        resultado.append(novo_item)

    # Filtro existente
    resultado = [item for item in resultado if item['PRODUTO'] == 'GERENCIAMENTO DE OBRA RESIDENCIAL' and item['INICIO'] is not None and item['RCR'] != '']
    return resultado

# Exemplo de uso e salvamento em CSV
if __name__ == "__main__":
    board_id = 926240878
    dados = get_dataMonday(board_id)
    df = pd.DataFrame(dados)
    
    # Salvar CSV com as novas colunas
    df.to_csv('monday_dados.csv', index=False, encoding='utf-8-sig')
    print("Arquivo salvo com sucesso!")
    print("\nPrimeiras linhas:")
    print(df.head())
    
    # Mostrar contagem por estado
    print("\nContagem por Estado:")
    print(df['ESTADO'].value_counts())




"""
Lógica de extração do estado:

Procurar por padrões como "SP, Brasil", "- SP, Brasil"
"State of São Paulo" → "SP"
"State of Alagoas" → "AL"
Para casos que não conseguir identificar, deixar "N/A"

"""