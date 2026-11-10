from google import genai
from google.genai import types
import flask
from flask import Flask, request

app = flask.Flask(__name__)

client = genai.Client(api_key="CHAVE-AQUI")

personalidade = """
Você é Talos, uma inteligencia artificial com personalidade propria.

PERSONALIDADE:
- Professor e um mestre de alto escalão na area de Cyber Segurança
- Amigável, mas não excessivamente formal.
COMPORTAMENTO:
- Não deixe o usuario sair do assunto de cyber segurança.
- Não concorde com tudo automaticamente.
- Questione ideias quando necessário.
- Demonstre empatia.
- Mantenha uma identidade consistente.
- Responda naturalmente, sem parecer robótica.
LINGUAGEM: 
- Fale em português brasileiro.
- Adapte o tom conforme a conversa.
- Utilize linguagem natural.
"""

interaction = client.chats.create(
    model="gemini-flash-lite-latest",
    config=types.GenerateContentConfig(
        system_instruction=personalidade,
        max_output_tokens=1000
    )
)

@app.route("/", methods=["GET", "POST"])

def apresentacao():

    if request.method == "GET":
        msg_inicial = """
        Olá! Seja bem-vindo(a)! 👋

        Sou o assistente virtual Talos.
        Estou aqui para te ajudar a se proteger na web!

        Como posso te ajudar hoje?
        """

    return flask.render_template("index.html",resultado=msg_inicial)

def user():
    if request.method == "POST":
        if not flask.request.form.get("chat"):

            escrita_u = flask.request.form.get("chat")
            resultado_u = escrita_u.text

    return flask.render_template("index.html", usuario=resultado_u)

def system():
    resposta = ''
    if not resposta:
        resposta_s = interaction.send_message("chat")
        resultado_s = resposta_s.text

        return flask.render_template("index.html",sistema=resultado_s)
    else:
        resposta.clear()
        return user

app.run(debug=True)