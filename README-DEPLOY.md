# 🚀 Guia de Deploy - TOOLS Calculator

## 🔒 Configuração de Credenciais

Este projeto usa **abordagem híbrida** para gerenciar credenciais de forma segura:

### 📁 **Arquivos de Configuração**

- `.streamlit/secrets.toml` - Para Streamlit Cloud
- `.env` - Para desenvolvimento local
- Ambos estão no `.gitignore` e **NÃO são versionados**

---

## ☁️ **Deploy no Streamlit Cloud**

### 1. **Configurar Secrets no Streamlit Cloud:**

```toml
# Acesse: https://share.streamlit.io/[seu-app]/settings
# Vá em "Secrets" e adicione:

MONGO_URI = "sua_mongo_uri_aqui"

[monday]
API_KEY = "sua_api_key_aqui"
BOARD_ID = 926240878
```

### 2. **Deploy:**

- Faça push do código (sem os arquivos .env e secrets.toml)
- O Streamlit Cloud usará os secrets configurados

---

## 🖥️ **Desenvolvimento Local**

### 1. **Usar o arquivo .env:**

```bash
# O arquivo .env já está criado com as credenciais
# O sistema carrega automaticamente
```

### 2. **Ou usar secrets.toml:**

```bash
# O arquivo .streamlit/secrets.toml também funciona localmente
# Útil para testar exatamente como na nuvem
```

---

## 🔧 **Como Funciona**

A função `get_credentials()` em `config_utils.py`:

1. **1ª Tentativa:** `st.secrets` (Streamlit Cloud)
2. **2ª Tentativa:** Variáveis de ambiente (arquivo .env)
3. **Fallback:** Erro explicativo se nenhum método funcionar

---

## ⚠️ **Importante**

- **NUNCA** commite arquivos com credenciais
- **SEMPRE** use variáveis de ambiente em produção
- **TESTE** localmente antes do deploy
- **MANTENHA** credenciais atualizadas

---

## 🛠️ **Outras Plataformas**

### **Heroku:**

```bash
heroku config:set MONGO_URI="sua_uri"
heroku config:set MONDAY_API_KEY="sua_key"
heroku config:set MONDAY_BOARD_ID=926240878
```

### **Docker:**

```dockerfile
ENV MONGO_URI=sua_uri
ENV MONDAY_API_KEY=sua_key
ENV MONDAY_BOARD_ID=926240878
```

### **AWS/GCP/Azure:**

Use os respectivos serviços de gerenciamento de secrets.
