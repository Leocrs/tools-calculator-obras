import requests

url = "https://indiceseconomicos.secovi.com.br/indicadormensal.php?idindicador=59"
params = {"indicator": 59}

response = requests.get(url, params=params)

if response.status_code == 200:
    print(response.text)
else:
    print("Erro:", response.status_code)
    
    
 
 