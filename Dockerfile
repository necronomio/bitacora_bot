# Usar Python 3.11 oficial
FROM python:3.11-slim

# Establecer directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos primero (para caché)
COPY requirements.txt .
COPY runtime.txt .

# Instalar dependencias
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto del código
COPY bot_bitacora.py .

# Variables de entorno
ENV PYTHONUNBUFFERED=1

# Comando para ejecutar el bot
CMD ["python", "bot_bitacora.py"]
