#!/bin/bash
# Railway start script

# PORTが設定されていない場合のデフォルト値
PORT=${PORT:-8501}

# Streamlitアプリケーションを起動
exec streamlit run app.py \
    --server.port=${PORT} \
    --server.address=0.0.0.0 \
    --server.headless=true \
    --server.fileWatcherType=none