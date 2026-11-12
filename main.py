import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import flask
from flask import Flask, request, render_template, redirect, url_for, session, flash
import psycopg2

load_dotenv()

connect = psycopg2.connect(
    host="127.0.0.1",
    port="5432",
    database="",
    user="postgres",
    password="postgres" 
)

app = flask.Flask(__name__)

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

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

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")

        if not email or not senha:
            flash("Preencha todos os campos")
            return redirect(url_for("cadastro"))

        if len(senha) <8:
            flash("Sua senha deve conter no minimo 8 caracteres")
            return redirect(url_for("cadastro"))

        try:
            cursor = connect.cursor()

            cursor.execute("SELECT id_usu,email_usu FROM loggin WHERE email_usu = %s", (email,))
            cadastrar = cursor.fetchone()
            if not cadastrar:
                cursor.execute("INSERT INTO loggin (email_usu,senha_usu) VALUES (%s,%s) RETURNING id_usu", (email,senha))
                connect.commit()

        except Exception as erro:
            connect.rollback()
            flash("Erro ao criar sua conta")

        finally:
            cursor.close()

    return render_template("cadastro.html")


@app.route("/", methods=["GET", "POST"])

def apresentacao():

    msg_inicial = """
    Olá! Seja bem-vindo(a)! 👋

    Sou o assistente virtual Talos.
    Estou aqui para te ajudar a se proteger na web!

    Como posso te ajudar hoje?
    """

    if request.method == "GET":

        return render_template("index.html",apresentar=msg_inicial)

    escrita_u = request.form.get("chat", "").strip()

    if not escrita_u:
        return render_template("index.html",apresentar=msg_inicial)

    try:
        resposta_s = interaction.send_message(escrita_u)
        resultado_s = resposta_s.text

    except Exception as erro:
        print(f"Erro: {erro}")
        resultado_s = "Ocorreu um erro ao processar sua mensagem."

    return render_template(
        "index.html",
        apresentar=msg_inicial,
        usuario=escrita_u,
        sistema=resultado_s)



app.run(debug=True)
