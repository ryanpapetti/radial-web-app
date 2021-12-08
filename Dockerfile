# FROM tiangolo/uwsgi-nginx-flask:python3.8


FROM python:3.8-slim-buster
USER root

WORKDIR /var/www/radial-web-app

RUN apt-get update
RUN apt-get install python3-pip python3-dev nginx zip gcc musl-dev unzip nano systemd -y

#prepare and copy configs
RUN rm -rf /etc/nginx/sites-available/default
RUN rm -rf /etc/nginx/sites-enabled/default
COPY default /etc/nginx/sites-available/
RUN ln -s /etc/nginx/sites-available/default /etc/nginx/sites-enabled/

COPY . .

#  Create the environment:
RUN pip3 install --upgrade pip
RUN pip3 install -r app/requirements.txt
RUN pip3 install uwsgi

# chown www dir
RUN chown -R www-data:www-data /var/www/radial-web-app
RUN chmod -R 755 /var/www/radial-web-app

# ENV LISTEN_PORT 9000
EXPOSE 9000

CMD  ["/var/www/radial-web-app/entrypoint.sh"]

