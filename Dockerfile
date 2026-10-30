FROM mcr.microsoft.com/playwright/python:v1.52.0-jammy
WORKDIR /app
COPY test_dashboard.py /app/test_dashboard.py
CMD ["python", "/app/test_dashboard.py"]
