# Imagen base ligera
FROM python:3.11-slim

# Evita preguntas interactuando con apt
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    gnupg \
    unixodbc \
    unixodbc-dev \
    && rm -rf /var/lib/apt/lists/*

# Instalar Microsoft ODBC Driver 17 para SQL Server
RUN curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - && \
    curl https://packages.microsoft.com/config/debian/11/prod.list > /etc/apt/sources.list.d/mssql-release.list && \
    apt-get update && ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Crear directorio de trabajo
WORKDIR /app

# Copiar requirements
COPY requirements.txt requirements.txt

# Instalar dependencias Python
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar aplicación completa
COPY . .

# Puerto usado en Railway
ENV PORT=8080

# Comando de inicio
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "wsgi:app"]
