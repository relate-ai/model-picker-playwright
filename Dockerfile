FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy
WORKDIR /app
RUN pip install --no-cache-dir playwright==1.52.0
COPY test_dashboard.py /app/test_dashboard.py
CMD ["sh", "-c", "python3 /app/test_dashboard.py > /app/screenshots/container.log 2>&1"]
