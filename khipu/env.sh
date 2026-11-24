#!/bin/bash
# Entorno comun del Laboratorio 4 en Khipu. Se hace `source` desde los scripts de Slurm.
module load python3/3.11.11
module load cuda/12.6
source $HOME/venvs/lab4/bin/activate
export LAB4_ROOT=$HOME/lab4
export LAB4_BASE=$LAB4_ROOT/Laboratorio4/work          # datos, indices, audios, resultados
export LAB4_STORE=$LAB4_ROOT/Laboratorio4/work/store   # base SQLite de la tienda
export HF_HOME=$LAB4_ROOT/hf_cache
export TTS_HOME=$LAB4_ROOT/tts_cache
export NLTK_DATA=$LAB4_ROOT/nltk_data
export COQUI_TOS_AGREED=1
export MPLBACKEND=Agg
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
cd $LAB4_ROOT/Laboratorio4/solucion
