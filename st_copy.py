import streamlit as st
import streamlit.components.v1 as components

def copy_button(text_to_copy, icon='material_symbols', tooltip='Copiar', copied_label='Copiado!', key=None):
    """
    Cria um botão de cópia usando Streamlit
    
    Args:
        text_to_copy (str): Texto a ser copiado
        icon (str): Ícone do botão (não usado nesta implementação)
        tooltip (str): Tooltip do botão
        copied_label (str): Label mostrado após copiar
        key (str): Key única para o botão
    """
    
    # HTML e JavaScript para o botão de cópia
    copy_html = f"""
    <div>
        <button 
            onclick="copyToClipboard()" 
            style="
                background-color: #ff4b4b;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                margin: 5px 0;
            "
            title="{tooltip}"
            id="copy-btn-{key or 'default'}"
        >
            📋 Copiar
        </button>
        <span id="copy-status-{key or 'default'}" style="margin-left: 10px; color: green; display: none;">
            {copied_label}
        </span>
    </div>
    
    <script>
    function copyToClipboard() {{
        const text = `{text_to_copy}`;
        navigator.clipboard.writeText(text).then(function() {{
            const btn = document.getElementById('copy-btn-{key or 'default'}');
            const status = document.getElementById('copy-status-{key or 'default'}');
            
            status.style.display = 'inline';
            setTimeout(function() {{
                status.style.display = 'none';
            }}, 2000);
        }}, function(err) {{
            console.error('Erro ao copiar: ', err);
        }});
    }}
    </script>
    """
    
    # Renderiza o HTML
    components.html(copy_html, height=60)