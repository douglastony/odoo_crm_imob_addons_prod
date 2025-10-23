#!/bin/bash
# Script para rodar os testes do módulo crm_sales_unit

CONTAINER="odoo-test_odoo_test_app.1.wl043ihsik467pvk36xgkh4pc"
DB_NAME="odoo_test"
DB_HOST="odoo_test_db"
DB_USER="odoo_test"
DB_PASSWORD="senha_forte_para_teste"
MODULE="crm_sales_unit"

docker exec -it $CONTAINER \
    odoo -d $DB_NAME -u $MODULE \
    --db_host=$DB_HOST \
    --db_user=$DB_USER \
    --db_password=$DB_PASSWORD \
    --test-enable --stop-after-init \
    --http-port=8072
