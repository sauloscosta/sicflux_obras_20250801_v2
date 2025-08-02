from flask import Flask, request, jsonify, send_file, render_template_string
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os
from urllib.parse import urljoin

app = Flask(__name__)
PORTAIS = ["https://abrava.com.br/associados/"]
KEYWORDS = ["ar-condicionado", "ventilação", "HVAC", "PMOC", "climatização"]

# Histórico de coletas (simples em memória)
coletas_historico = []

def extrair_editais(url):
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        registros = []
        for link in soup.find_all("a", href=True):
            texto = link.get_text().strip()
            full_url = urljoin(url, link["href"])
            if any(k in texto.lower() for k in KEYWORDS):
                registros.append({
                    "Título": texto,
                    "Link": full_url,
                    "Fonte": url,
                    "PDF Match": "N/A",
                    "Data de Extração": datetime.now().strftime("%Y-%m-%d")
                })
        return registros
    except:
        return []

def coletar_dados(filtro_estado=None, filtro_data_min=None):
    todos_registros = []
    for portal in PORTAIS:
        try:
            registros = extrair_editais(portal)
            todos_registros.extend(registros)
        except Exception as e:
            print(f"Erro ao acessar {portal}: {e}")

    df = pd.DataFrame(todos_registros)
    if filtro_estado:
        df = df[df['Fonte'].str.contains(filtro_estado, case=False, na=False)]
    if filtro_data_min:
        df['Data de Extração'] = pd.to_datetime(df['Data de Extração'])
        df = df[df['Data de Extração'] >= pd.to_datetime(filtro_data_min)]
    return df

def exportar_para_excel(df, caminho="resultado_hvac.xlsx"):
    df.to_excel(caminho, index=False)
    return caminho

@app.route("/api/coletar", methods=["GET"])
def api_coletar():
    estado = request.args.get("estado")
    dias = request.args.get("dias")
    filtro_data = None
    if dias and dias.isdigit():
        dias = int(dias)
        filtro_data = datetime.now() - pd.to_timedelta(dias, unit="d")

    df = coletar_dados(filtro_estado=estado, filtro_data_min=filtro_data)
    if df.empty:
        return jsonify({"mensagem": "Nenhum edital encontrado com os filtros aplicados."}), 404
    else:
        caminho = exportar_para_excel(df)
        coletas_historico.append({
            "data": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "estado": estado or "Todos",
            "dias": dias or "Todos",
            "quantidade": len(df)
        })
        return send_file(caminho, as_attachment=True)

@app.route("/historico")
def historico():
    rows = "".join([
        f"<tr><td>{c['data']}</td><td>{c['estado']}</td><td>{c['dias']}</td><td>{c['quantidade']}</td></tr>"
        for c in coletas_historico
    ])
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Histórico de Coletas - SICFLUX</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 30px; background-color: #f0f2f5; }}
            table {{ width: 100%; border-collapse: collapse; background: #fff; }}
            th, td {{ padding: 10px; border: 1px solid #ccc; text-align: center; }}
            th {{ background-color: #007C91; color: white; }}
            h2 {{ color: #007C91; }}
            a {{ text-decoration: none; color: #00A8A3; }}
        </style>
    </head>
    <body>
        <h2>Histórico de Coletas HVAC</h2>
        <p><a href="/">← Voltar à Página Inicial</a></p>
        <table>
            <tr><th>Data</th><th>Estado</th><th>Período (dias)</th><th>Registros</th></tr>
            {rows or '<tr><td colspan="4">Nenhuma coleta registrada ainda.</td></tr>'}
        </table>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route("/")
def home():
    return "<h1>Aplicação SICFLUX HVAC Ativa</h1><p>Use /api/coletar ou /historico</p>"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
