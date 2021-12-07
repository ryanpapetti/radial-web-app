# FROM ubuntu:18.04
FROM continuumio/miniconda3
FROM tiangolo/uwsgi-nginx-flask:python3.8

ENV LISTEN_PORT 9000
EXPOSE 9000

COPY ./app app


# Make RUN commands use `bash --login`:
SHELL ["/bin/bash", "--login", "-c"]

RUN apt-get update
RUN apt-get install python3-pip python3-dev nginx zip gcc musl-dev unzip nano systemd ffmpeg -y

#  Create the environment:
COPY environment.yml .
RUN conda env create -f environment.yml

# Initialize conda in bash config fiiles:
RUN conda init bash

# Activate the environment, and make sure it's activated:
RUN echo "conda activate radial-web-app" > ~/.bashrc

RUN conda activate radial-web-app

COPY entrypoint.sh .

EXPOSE 80

# ENTRYPOINT ["conda", "run", "--no-capture-output", "-n", "radial-web-app", "python", "main.py"]
