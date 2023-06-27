import os
import json
import logging
from flask import Flask, request
from jit import jit_cleaner

logging.basicConfig()

app = Flask(__name__)


@app.route("/hello")
def hello_world():
    """Example Hello World route."""
    name = os.environ.get("NAME", "World")
    return f"Hello {name}!"

@app.route("/scheduler", methods=['POST'])
def scheduler():
    """cloud scheduler handler"""
    content_type = request.headers.get('Content-Type')
    if content_type != 'application/json':
        return "Content type is not supported."

    jit_cleaner.jit_cleaner()
    return json.dumps({})

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))