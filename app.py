from flask import Flask

from lex import configure_app

app = Flask(__name__)
configure_app(app)
