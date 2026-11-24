#!/bin/bash
while pgrep -u $USER -f install.sh >/dev/null; do sleep 15; done
grep -q INSTALL_OK $HOME/lab4/logs/install.log || { echo "instalacion fallida"; exit 1; }
source $HOME/lab4/env.sh
python $HOME/lab4/prefetch.py && cd $HOME/lab4 && sbatch run_all.sbatch
