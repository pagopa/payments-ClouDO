# Official base image for Azure Functions Python (Functions v4, Python 3.12)
FROM mcr.microsoft.com/azure-functions/python:4-python3.12

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

# Switch back to the default user used by the Functions runtime
USER www-data

# Install Python dependencies
COPY requirements.txt /home/site/wwwroot/requirements.txt
RUN python -m pip install --no-cache-dir -r /home/site/wwwroot/requirements.txt

# Copy the Function App code
COPY . /home/site/wwwroot
