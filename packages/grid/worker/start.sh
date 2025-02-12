#! /usr/bin/env bash
set -e

echo "Running start.sh with RELEASE=${RELEASE}"

RELOAD=""
if [[ ${DEV_MODE} == "True" ]];
then
    echo "DEV_MODE Enabled"
    RELOAD="--reload"
    pip install -e "/app/syft[telemetry]"
fi

export RUST_BACKTRACE=$RUST_BACKTRACE

set +e
NODE_PRIVATE_KEY=$(python bootstrap.py --private_key)
NODE_UID=$(python bootstrap.py --uid)
set -e

echo "NODE_PRIVATE_KEY=$NODE_PRIVATE_KEY"
echo "NODE_UID=$NODE_UID"
echo "NODE_TYPE=$NODE_TYPE"

export NODE_UID=$NODE_UID
export NODE_PRIVATE_KEY=$NODE_PRIVATE_KEY

APP_MODULE=worker:app
LOG_LEVEL=${LOG_LEVEL:-info}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8080}

exec uvicorn $RELOAD --host $HOST --port $PORT --log-level $LOG_LEVEL "$APP_MODULE"
