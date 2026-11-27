import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import flask
from flask import Flask, request, render_template, redirect, url_for, session, flash
import psycopg2
from datetime import date
import secrets

load_dotenv()

app = flask.Flask(__name__)

app.secret_key = "76073305bdf6f008cfe57b29c39b3b5ad3e1a88cecdaabc27d8d703d2b3a922b"


def conectar():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
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

configuracao_chat = types.GenerateContentConfig(
    system_instruction=personalidade,
    max_output_tokens=1000
)

def listar_conversas(cursor, id_usuario):
    cursor.execute("""
        SELECT c.id_conversa,
               CASE
                   WHEN c.descricao = 'Nova conversa' THEN COALESCE(
                       (
                           SELECT CASE
                               WHEN char_length(m.mensagens) > 45
                               THEN left(m.mensagens, 42) || '...'
                               ELSE m.mensagens
                           END
                           FROM mensagem AS m
                           WHERE m.id_conversa = c.id_conversa
                             AND m.proprietario = 'usuario'
                           ORDER BY m.id_msg ASC
                           LIMIT 1
                       ),
                       c.descricao
                   )
                   ELSE c.descricao
               END AS descricao
        FROM conversa AS c
        WHERE c.id_usu = %s
          AND EXISTS (
              SELECT 1
              FROM mensagem AS m
              WHERE m.id_conversa = c.id_conversa
          )
        ORDER BY c.id_conversa DESC
    """, (id_usuario,))

    return cursor.fetchall()


@app.route("/", methods=["GET", "POST"])
def conversa():
    if "id_usu" not in session:
        return redirect(url_for("cadastro"))

    id_usuario = session["id_usu"]
    msg_inicial = "Olá! Sou o Talos. Como posso ajudar você hoje?"

    conn = None
    cursor = None

    try:
        conn = conectar()
        cursor = conn.cursor()

        if request.method == "POST" and request.form.get("acao") == "nova_conversa":
            session.pop("conversa_ativa", None)
            session["nova_conversa"] = True

            return redirect(url_for("conversa"))

        id_solicitado = request.form.get("id_conversa") if request.method == "POST" else request.args.get("id_conversa")

        if id_solicitado and request.form.get("chat") is None:
            cursor.execute("""SELECT id_conversa FROM conversa WHERE id_conversa = %s AND id_usu = %s""", (id_solicitado, id_usuario))

            resultado = cursor.fetchone()

            if not resultado:
                flash("Conversa não encontrada.")
                return redirect(url_for("conversa"))

            session["conversa_ativa"] = resultado[0]

            return redirect(url_for("conversa"))

        id_conversa = session.get("conversa_ativa")

        if id_conversa:
            cursor.execute("""SELECT id_conversa FROM conversa WHERE id_conversa = %s AND id_usu = %s""", (id_conversa, id_usuario))

            resultado = cursor.fetchone()

            if not resultado:
                session.pop("conversa_ativa", None)
                id_conversa = None

        if not id_conversa:
            id_conversa = None

        if request.method == "POST" and request.form.get("chat") is not None:
            texto_usuario = request.form.get("chat", "").strip()

            if texto_usuario and not id_conversa:
                cursor.execute("""INSERT INTO conversa (id_usu, descricao) VALUES (%s, %s) RETURNING id_conversa""", (id_usuario, "Nova conversa"))

                id_conversa = cursor.fetchone()[0]

                session["conversa_ativa"] = id_conversa
                session.pop("nova_conversa", None)

                historico = [
                    types.Content(
                        role="user" if autor == "usuario" else "model",
                        parts=[types.Part.from_text(text=texto)]
                    )
                    for autor, texto in cursor.fetchall()
                ]

                chat_atual = client.chats.create(
                    model="gemini-flash-lite-latest",
                    config=configuracao_chat,
                    history=historico
                )

                resposta = chat_atual.send_message(texto_usuario)
                texto_bot = resposta.text or "Não consegui gerar uma resposta."

                cursor.execute("""INSERT INTO mensagem (id_conversa, mensagens, proprietario) VALUES (%s, %s, %s)""", (id_conversa, texto_usuario, "usuario"))

                cursor.execute("""INSERT INTO mensagem (id_conversa, mensagens, proprietario) VALUES (%s, %s, %s)""", (id_conversa, texto_bot, "bot"))

                titulo = texto_usuario.replace("\n", " ").strip()

                if len(titulo) > 45:
                    titulo = titulo[:42].rstrip() + "..."

                cursor.execute("""
                    UPDATE conversa
                    SET descricao = %s
                    WHERE id_conversa = %s
                      AND id_usu = %s
                      AND descricao = %s
                """, (titulo, id_conversa, id_usuario, "Nova conversa"))

                conn.commit()

                return redirect(url_for("conversa"))

        cursor.execute("""SELECT proprietario, mensagens FROM mensagem WHERE id_conversa = %s ORDER BY id_msg ASC""", (id_conversa,))

        mensagens = cursor.fetchall()

        conversas = listar_conversas(cursor, id_usuario)

        return render_template(
            "index.html",
            apresentar=msg_inicial,
            mensagens=mensagens,
            conversas=conversas,
            conversa_ativa=id_conversa
        )

    except Exception:
        app.logger.exception("Falha ao carregar ou enviar mensagem")

        if conn is not None:
            conn.rollback()

        flash("Ocorreu um erro ao carregar ou enviar a mensagem.")
        return redirect(url_for("conversa"))

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    data_atual = date.today()
    if request.method == "POST":
        email = request.form.get("email","").strip().lower()
        senha = request.form.get("senha","")

        if not email or not senha:
            flash("Preencha todos os campos.", "error")
            return redirect(url_for("cadastro"))

        if len(senha) <8:
            flash("Sua senha deve conter no mínimo 8 caracteres.", "error")
            return redirect(url_for("cadastro"))

        conn = None
        cursor = None

        try:
            conn = conectar()
            cursor = conn.cursor()

            cursor.execute("SELECT id_usu,email_usu FROM loggin WHERE email_usu = %s", (email,))
            cadastrar = cursor.fetchone()
            if cadastrar:
                flash("Este email já está cadastrado!", "error")
                return redirect(url_for("cadastro"))
                
            cursor.execute("INSERT INTO loggin (email_usu,senha_usu,data_criacao) VALUES (%s,%s,%s) RETURNING id_usu", (email,senha,data_atual))

            conn.commit()
            flash("Cadastro realizado com sucesso!", "success")
            return redirect(url_for("login"))

        except Exception as erro:
            app.logger.exception("Falha ao cadastrar usuário no banco")
            if conn is not None:
                conn.rollback()
            flash("Não foi possível concluir o cadastro. Verifique os dados e tente novamente.")
        
        finally:
            if cursor is not None:
                cursor.close()
        
            if conn is not None:
                conn.close()

    return render_template("cadastro.html")

@app.route("/login", methods=["GET", "POST"])

def login():
    if request.method == "GET":
        return render_template("login.html")

    loginemail = request.form.get("loginemail", "").strip().lower()
    loginsenha = request.form.get("loginsenha", "")
    conn = None
    cursor = None
    try:
        conn = conectar()
        cursor = conn.cursor()

        cursor.execute("SELECT id_usu,email_usu,senha_usu FROM loggin WHERE email_usu = %s AND senha_usu = %s", (loginemail,loginsenha))

        usuario = cursor.fetchone()

        if usuario:
            session["id_usu"] = usuario [0]
            session["email"] = usuario [1]

            flash("Login realizado com sucesso! Bem-vindo ao Talos.", "success")

            return redirect(url_for("conversa"))
        else:
            flash("Email ou senha incorretos")
    except Exception as erro:
        app.logger.exception("Falha ao autenticar usuário")
        if conn is not None:
            conn.rollback()
            flash("Erro ao fazer login")

    finally:
        if cursor is not None:
            cursor.close()

        if conn is not None:
            conn.close()

    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Você saiu da sua conta.")
    return redirect(url_for("login"))

app.run(debug=True)
