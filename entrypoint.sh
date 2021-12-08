#!/bin/bash

echo "beginning script for web app"

pwd 

# start nginx webserver, as by default is is stopped
service nginx start

# run our python code via uwsgi
uwsgi --ini /var/www/radial-web-app/app/uwsgi.ini
