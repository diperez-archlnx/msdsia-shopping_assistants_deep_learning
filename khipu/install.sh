#!/bin/bash
set -e
module load python3/3.11.11
python3 -m venv $HOME/venvs/lab4
source $HOME/venvs/lab4/bin/activate
pip install -q --upgrade pip
pip install -q torch==2.8.0 torchaudio==2.8.0 --index-url https://download.pytorch.org/whl/cu126
pip install -q "coqui-tts>=0.27" six "sentence-transformers>=4.0" "transformers>=4.57,<5" "bitsandbytes>=0.45" accelerate tabulate \
    pandas pyarrow scipy nltk librosa soundfile matplotlib psutil jupyter nbconvert ipykernel
pip list 2>/dev/null | grep -iE "^(torch|torchaudio|transformers|coqui-tts|sentence-transformers|bitsandbytes|accelerate|pandas|numpy) "
echo INSTALL_OK
