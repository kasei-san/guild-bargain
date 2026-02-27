#!/bin/bash
pkill -f "streamlit run app.py" && echo "Streamlit を停止しました" || echo "Streamlit は起動していません"
