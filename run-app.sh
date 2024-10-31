#!/bin/sh

if lsof -i:5000 >/dev/null 2>&1; then
    echo 'a program is using port 5000; output of `lsof -i:5000`:'
    lsof -i:5000
elif ! systemctl status httpd | grep inactive >/dev/null 2>&1; then
    echo 'httpd service is running, and likely using port 5000'
    echo 'kill httpd as root with `systemctl stop httpd` first and try again'
else
    . demograder/secrets && gunicorn --bind 0.0.0.0:5000 'demograder:create_app()'
fi
