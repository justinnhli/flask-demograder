#!/bin/sh

. demograder/secrets && gunicorn --bind 0.0.0.0:5000 'demograder:create_app()'
