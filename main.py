import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import flask
from flask import Flask, request, render_template, redirect, url_for, session, flash
import psycopg2
from datetime import datetime
import secrets

load_dotenv()

app = flask.Flask(__name__)

app.secret_key = "76073305bdf6f008cfe57b29c39b3b5ad3e1a88cecdaabc27d8d703d2b3a922b"

connect = psycopg2.connect(
    host="172.17.18.109",
    port="5432",
    database="projeto_integrador",
    user="postgres",
    password="postgres" 
)

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

@app.route("/", methods=["GET", "POST"])

def apresentacao():

    # if "id_usu" not in session:
    #     return redirect(url_for("cadastro"))

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
        resultado_s = resposta_s.text or "Nao consegui gerar uma resposta."

    except Exception as erro:
        print(f"Erro: {erro}")
        resultado_s = "Ocorreu um erro ao processar sua mensagem."

    return render_template(
        "index.html",
        apresentar=msg_inicial,
        usuario=escrita_u,
        sistema=resultado_s)

def mensagens():
    if "id_usu" not in session:
        return redirect(url_for("cadastro"))
    acc_logada = session["id_usu"]

    cursor = connect.cursor()

    escrita_u = request.form.get("chat", "").strip()
    resposta_s = interaction.send_message(escrita_u)
    resultado_s = resposta_s.text or "Nao consegui gerar uma resposta."

    cursor.execute("""
    INSERT INTO mensagens (id_usu, remetente, conteudo)
    VALUES (%s, %s, %s)
    """, (acc_logada, "bot", resultado_s))

    return render_template(
        "index.html",
        usuario=escrita_u,
        sistema=resultado_s)



@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    data_atual = datetime.now().strftime("%d/%m/%Y")
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
                cursor.execute("INSERT INTO loggin (email_usu,senha_usu,data_criacao) VALUES (%s,%s,%s) RETURNING id_usu", (email,senha,data_atual))
                connect.commit()

        except Exception as erro:
            connect.rollback()
            flash("Erro ao criar sua conta")

    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])

def login():
    loginemail = request.form.get("loginemail", "").strip().lower()
    loginsenha = request.form.get("loginsenha", "")

    try:
        cursor = connect.cursor()

        cursor.execute("SELECT id_usu,email_usu,senha_usu FROM loggin WHERE email_usu = %s AND senha_usu = %s", (loginemail,loginsenha))

        usuario = cursor.fetchone()

        if usuario:
            session["id_usu"] = usuario [0]
            session["email"] = usuario [1]

            flash("Login realizado com sucesso! Bem-vindo ao Talos.", "success")

            return redirect(url_for("/"))
        else:
            flash("Email ou senha incorretos")
    except Exception as erro:
        connect.rollback()
        flash("Erro ao fazer login")

    return render_template("login.html")

app.run(debug=True)