FROM debian:11-slim AS build-env

# Adapted from https://github.com/GoogleContainerTools/distroless/blob/main/examples/python3-requirements/Dockerfile
# Build a virtualenv in the build container and copy this over to a distroless
# base for a compact final image.
RUN apt-get update && \
    apt-get install --no-install-suggests --no-install-recommends --yes \
    python3-venv gcc libpython3-dev git && \
    python3 -m venv /venv

ENV APP_HOME /app
WORKDIR $APP_HOME
COPY requirements.txt requirements.txt
RUN /venv/bin/pip install install --no-cache-dir -r requirements.txt


# "Distroless" images contain only your application and its runtime dependencies.
# https://github.com/GoogleContainerTools/distroless
# https://github.com/GoogleContainerTools/distroless/blob/main/examples/python3/Dockerfile
FROM gcr.io/distroless/python3
ENV APP_HOME /app

COPY --from=build-env /venv /venv
WORKDIR $APP_HOME
COPY . ./

# Allow statements and log messages to immediately appear in the logs
ENV PYTHONUNBUFFERED True
ENV PYTHONPATH $APP_HOME

# Run the web service on container startup. Here we use the gunicorn
# webserver, with one worker process and 8 threads.
# For environments with multiple CPU cores, increase the number of workers
# to be equal to the cores available.
# Timeout is set to 0 to disable the timeouts of the workers to allow Cloud Run to handle instance scaling.
ENTRYPOINT ["/venv/bin/gunicorn", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]
