FROM python:3.12-slim

WORKDIR /work

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLCONFIGDIR=/tmp/matplotlib

RUN pip install --no-cache-dir pandas numpy matplotlib seaborn scikit-learn scipy openpyxl tabulate

RUN useradd -m -u 1000 runner
USER runner
