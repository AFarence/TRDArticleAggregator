FROM python:3.10-slim

# Install OS-level dependencies required by browsers.
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
 && rm -rf /var/lib/apt/lists/*

# Set the working directory.
WORKDIR /app

# Copy requirements.txt and install Python dependencies.
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the rest of your app's code.
COPY . .

# Download Playwright browser binaries.
RUN playwright install

# Expose the default Streamlit port.
EXPOSE 8501

# Command to run your Streamlit app.
CMD ["streamlit", "run", "app.py", "--server.enableCORS", "false"]
