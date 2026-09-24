# Runs the adstxt workflow (graph.py) in a container.
#
# The image holds only the code. The API key comes in at run time from .env,
# and data/ and results/ are mounted from the host, so nothing private is baked in.
#
#   docker build -t adstxt-agent .
#   docker run --rm --env-file .env \
#     -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
#     adstxt-agent "data/uploads/<spreadsheet>.xlsx" --top 20

FROM python:3.12-slim

# The ads.txt checks shell out to curl.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY prompts/ prompts/

# Run as an ordinary user, not root.
RUN useradd --create-home app && mkdir -p data results && chown app:app data results
USER app

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python", "graph.py"]
CMD ["--help"]
