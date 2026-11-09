FROM python:3.11-slim-bookworm AS kyoki-base

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# update apt
RUN apt-get update && apt-get -y upgrade

# install dependencies
RUN apt-get install -y --no-install-recommends \
    gcc git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

# setup user
RUN groupadd -o -g $GID player
RUN useradd player --create-home -u $UID -g $GID -m -s /bin/bash 
USER player

WORKDIR /home/player/kyoki

COPY requirements.txt .
RUN pip install --user -r requirements.txt

# copy all files
COPY . .

EXPOSE 1337

FROM kyoki-base AS kyoki-dev

CMD ["python3", "-m", "uvicorn", "app.main:app", "--lifespan", "on", "--host", "0.0.0.0", "--port", "1337", "--reload"]

FROM python:3.11-slim-bookworm AS kyoki-prod

ARG UID=1000
ARG GID=1000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/player/.local/bin:${PATH}"

# setup user
RUN groupadd -o -g $GID player
RUN useradd player --create-home -u $UID -g $GID -m -s /bin/bash
USER player

WORKDIR /home/player/kyoki

COPY --from=kyoki-base /home/player/.local /home/player/.local
COPY requirements.txt .
COPY app ./app

EXPOSE 1337

HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:1337/health').read()"

CMD ["fastapi", "run", "app/main.py", "--port", "1337", "--workers", "1", "--proxy-headers"]
