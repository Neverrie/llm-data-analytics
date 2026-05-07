FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV MPLBACKEND=Agg
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUTF8=1

RUN pip install --no-cache-dir \
    pandas==2.2.3 \
    numpy \
    matplotlib==3.9.2 \
    seaborn==0.13.2 \
    scipy==1.14.1 \
    scikit-learn==1.5.2 \
    openpyxl==3.1.5

RUN useradd -m -u 1000 runner
USER runner
WORKDIR /work
