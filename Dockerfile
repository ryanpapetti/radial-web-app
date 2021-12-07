# FROM tiangolo/uwsgi-nginx-flask:python3.8


FROM python:3.8-slim-buster
USER root

WORKDIR /var/www/radial-web-app


COPY ./app app


RUN apt-get update
RUN apt-get install python3-pip python3-dev nginx zip gcc musl-dev unzip nano systemd -y

#prepare and copy configs
RUN rm -rf /etc/nginx/sites-available/default
RUN rm -rf /etc/nginx/sites-enabled/default
COPY default /etc/nginx/sites-available/
RUN ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/

#  Create the environment:
RUN pip3 install --upgrade pip
RUN pip3 install -r app/requirements.txt
RUN pip3 install uwsgi

# COPY nginx_config.conf /etc/nginx/conf.d/virtual.conf

# COPY flask-app-conf /etc/nginx/sites-enabled/default
# COPY nginx_config.conf /etc/nginx/sites-enabled/default

COPY entrypoint.sh /entrypoint.sh

# ENV LISTEN_PORT 9000
EXPOSE 9000

# EXPOSE 80
RUN chmod +x entrypoint.sh
CMD  ["./entrypoint.sh"]

