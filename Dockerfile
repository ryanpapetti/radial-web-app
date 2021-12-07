FROM tiangolo/uwsgi-nginx-flask:python3.8

ENV LISTEN_PORT 9000
EXPOSE 9000

COPY ./app app

RUN apt-get update
RUN apt-get install python3-pip python3-dev nginx zip gcc musl-dev unzip nano systemd ffmpeg -y

#  Create the environment:
RUN pip3 install -r app/requirements.txt

COPY entrypoint.sh .

EXPOSE 80
RUN chmod +x entrypoint.sh
CMD  ["./entrypoint.sh"]

