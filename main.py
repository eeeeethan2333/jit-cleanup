import json
import logging
import os

from flask import Flask
from flask import request

from jit.core import jit_cleaner
from jit.utils import config

logger = logging.getLogger("my-app")
# Convenient methods in order of verbosity from highest to lowest
logger.debug("this will get printed")
logger.info("this will get printed")
logger.warning("this will get printed")
logger.error("this will get printed")
logger.critical("this will get printed")

app = Flask(__name__)

conf = config.parse_env()


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

    jit_cleaner.run_jit_cleaner(conf)
    return json.dumps({})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
