# Official base image for Azure Functions Python (Functions v4, Python 3.12)
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

ARG APP_PATH=.

# Helpful environment variables
ENV AzureWebJobsScriptRoot=/home/site/wwwroot \
    AzureFunctionsJobHost__Logging__Console__IsEnabled=true \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# (Optional but recommended) Install tzdata to ensure proper zoneinfo behavior
USER root
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends tzdata && \
    rm -rf /var/lib/apt/lists/*

# Copy only requirements first to leverage Docker layer cache
COPY ${APP_PATH}/requirements.txt /tmp/requirements.txt

# Install Python dependencies into the Functions runtime folder to avoid permission issues
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the Function App code
COPY ${APP_PATH}/ /home/site/wwwroot/
