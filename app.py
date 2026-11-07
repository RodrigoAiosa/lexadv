"""Ponto de entrada da aplicação LEX.

Desenvolvimento:  python app.py
Produção:         gunicorn app:app
Vercel:           detecta o objeto `app` deste arquivo (precisa instanciar Flask aqui).
"""
import os

from flask import Flask

from lex import configure_app

app = Flask(__name__)
configure_app(app)

if __name__ == "__main__":
    app.run(
        host=os.environ.get("HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
