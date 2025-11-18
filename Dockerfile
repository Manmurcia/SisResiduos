# Imagen base
FROM python:3.13-slim

# Crear directorio de trabajo
WORKDIR /app

# Copiar requerimientos
COPY requirements.txt .

# Instalar dependencias de sistema necesarias
RUN apt-get update && \
    apt-get install -y curl gnupg unixodbc-dev build-essential

# Descargar y registrar la clave GPG de Microsoft
RUN curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor \
    | tee /usr/share/keyrings/microsoft-prod.gpg > /dev/null

# Agregar repositorio oficial de Microsoft para msodbcsql17
RUN echo "deb [signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
    | tee /etc/apt/sources.list.d/microsoft-prod.list

# Instalar Microsoft ODBC Driver 17
RUN apt-get update && \
    ACCEPT_EULA=Y apt-get install -y msodbcsql17 && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar todo el proyecto
COPY . .

# Exponer puerto usado por Railway
EXPOSE 8080

# Comando de inicio
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:crear_app()"]
