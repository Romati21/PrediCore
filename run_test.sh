#!/bin/bash

export ENV=development

cd /media/D/cnc_base_test
source venv_dev/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8343 --ssl-keyfile key.pem --ssl-certfile cert.pem
