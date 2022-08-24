#!/bin/sh

. demograder/secrets && gunicorn --bind 0.0.0.0:5000 --access-logfile logs/access.log --error-logfile logs/error.log 'demograder:create_app()'
