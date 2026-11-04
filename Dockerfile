# Rührwerk als Container-Image (Python 3.11, wie Debian 12)
FROM python:3.11-slim

# Kein .pyc-Müll, Ausgabe sofort sichtbar
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data

WORKDIR /srv/ruehrwerk
COPY pyproject.toml ./
COPY app ./app
COPY web ./web
# Editierbar installieren: so liegt der Ordner web/ neben dem Code, wo app/main.py ihn erwartet
RUN pip install --no-cache-dir -e .

# Eigener Benutzer statt root; /data ist das Volume für die Datenbank
RUN useradd --system --create-home --uid 10001 ruehrwerk && mkdir -p /data && chown ruehrwerk /data
USER ruehrwerk
VOLUME ["/data"]
EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8080/api/status', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
