#!/bin/bash
#SBATCH --job-name=lab4-voz
#SBATCH --partition=gpu
#SBATCH --gres=gpu:a100_3g.20gb:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=48G
#SBATCH --time=07:59:00
#SBATCH --output=/home/diego.perez/lab4/logs/lab4_%j.log
source $HOME/lab4/env.sh
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
echo "=== nodo $(hostname) | $(date) ==="; nvidia-smi
# La voz real del grupo es la referencia de la clonacion (run_local la busca en audios/sinteticos)
mkdir -p $LAB4_BASE/audios/sinteticos
cp -n $LAB4_BASE/audios/referencia.wav $LAB4_BASE/audios/sinteticos/referencia.wav
python tests/test_unit.py || exit 1
for etapa in ${LAB4_STAGES:-data retrieval scenarios voice}; do
  echo "=================== ETAPA $etapa | $(date) ==================="
  python tests/run_local.py $etapa 2>&1 | tee $HOME/lab4/logs/etapa_${etapa}_${SLURM_JOB_ID}.log
  echo "=== etapa $etapa termino con codigo ${PIPESTATUS[0]} | $(date) ==="
done
echo "=== FIN $(date) ==="
