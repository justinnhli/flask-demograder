#!/bin/sh

source demograder/secrets
gunicorn -b localhost:5000 'demograder:create_app()'
