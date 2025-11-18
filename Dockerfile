FROM python:3.10-slim

# Evitar mensajes interactivos
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependencias necesarias para ODBC
RUN apt-get update && apt-get install -y \
    curl \
    gnupg \
    apt-transport-https \
    unixodbc \
    unixodbc-dev \
    build-essential

# Agregar repositorio de Microsoft SIN apt-key (método moderno)
RUN curl https://packages.microsoft.com/config/debian/12/prod.list \
    | tee /etc/apt/sources.list.d/mssql-release.list

# Importar clave GPG de Microsoft de manera correcta
RUN curl https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor \
    | tee /usr/share/keyrings/microsoft.gpg > /dev/null

# Instalar driver ODBC 17 y herramientas
RUN apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Crear carpeta
WORKDIR /app

# Instalar dependencias del proyecto
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código del proyecto
COPY . .

# Puerto para Railway
EXPOSE 8080

# Comando de arranque
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
