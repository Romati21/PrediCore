#!/usr/bin/env bash

export ENV=production

cd /media/D/cnc_base_prod
source venv_prod/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8443 --ssl-keyfile key.pem --ssl-certfile cert.pem
