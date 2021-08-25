# docker build -t filelist_service . -f Dockerfile_filelist_service
FROM python:3.9.1

LABEL Author="Mikael"

RUN mkdir /app
WORKDIR /app

COPY test.py .



ENTRYPOINT ["python", "test.py"]