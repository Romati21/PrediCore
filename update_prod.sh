#!/bin/bash
cd /media/D/cnc_base_prod
git pull origin master
source venv_prod/bin/activate
pip install -r requirements.txt
alembic upgrade head
systemctl restart your_app_service
