import json
import os

from flask import Flask
from flask import request

from jit.core import jit_cleaner
from jit.utils import config
from jit.utils.logger import jit_logger

app = Flask(__name__)
conf = config.parse_env()


@app.route("/scheduler", methods=['POST'])
def scheduler():
    """cloud scheduler handler"""
    jit_logger.info("scheduler api")
    content_type = request.headers.get('Content-Type')
    if content_type != 'application/json':
        return "Content type is not supported."

    jit_cleaner.run_jit_cleaner(conf)
    return json.dumps({})


if __name__ == "__main__":
    jit_logger.info("starting application at port: %s",
                    int(os.environ.get("PORT", 8080)))

    app.run(debug=True, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
