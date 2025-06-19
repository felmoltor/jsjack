# Use official Python 3 image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies required by Scrapy and pipenv
RUN apt-get update && apt-get install -y \
    && pip install --no-cache-dir pipenv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy Pipfile and Pipfile.lock
COPY Pipfile Pipfile.lock ./

# Copy Scrapy project files
COPY . .

# Install Python dependencies using pipenv
RUN pipenv install --deploy --system

# Set the default command (optional: run the Scrapy spider directly)
ENTRYPOINT ["python", "/app/jsjack.py" ]