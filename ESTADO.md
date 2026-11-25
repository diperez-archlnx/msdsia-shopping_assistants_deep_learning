# Estado del proyecto: Laboratorio 4, asistente de compras por voz

Última actualización: 25 de noviembre de 2026. **Entrega: 25 de noviembre** (video y código).

Este archivo es el punto de partida al clonar el repositorio en otra máquina: qué hay, qué se hizo, qué está corriendo en Khipu y qué falta.

## 0. Actualización del 25 de noviembre (prevalece sobre lo que sigue)

* **El notebook se ejecutó completo en Google Colab (Tesla T4)** el 24 de noviembre por la noche. El notebook con salidas, `RESULTADOS.md` y todos los artefactos están en Drive: `MyDrive/master/deeplearning/laboratorio04/` (`solucion/` y `work/`). Las rutas del notebook apuntan ahí.
* Cifras de Colab: nDCG@10 de 0,693 (BM25) a **0,777** (sistema completo); agente **19/22** (ablación sin reglas 10/22); voz **6/6**; 0 incumplimientos; 11,7 GB de VRAM; 28,6 s por turno. Fallan S08, S11 y S13 (causas en `README.md` §5.2).
* `README.md` §5 y `RESULTADOS.md` ya reflejan la ejecución de Colab. Los resultados de la corrida local anterior quedaron en `evidencias/ejecucion_local_referencia/RESULTADOS_ejecucion_local.md`.
* **Khipu ya no se usa**: el trabajo de CPU terminó por límite de tiempo y el de GPU (65210) se canceló.
* **Video**: `video/Laboratorio4_presentacion_video.pptx` (18 diapositivas, guion por persona en las notas del orador; reparto para 4 integrantes). Se regenera con `video/generar_presentacion.py`. La demostración (8 min) se hace en vivo en la sección 12 del notebook.
* Grabaciones reales de los 20 turnos de usuario: están en Drive (`work/audios_usuario_real/`), no en el repositorio (voz de un integrante; el repo es público). El notebook `solucion/Laboratorio4_Asistente_Voz.ipynb` del repo ya incluye la celda que las usa; esa variante (`..._VOZ_REAL.ipynb` en Drive) aún no se ha ejecutado.
* **Pendiente**: grabar el video y subir `solucion/` + video al formulario.

## 1. Qué contiene el repositorio

| Ruta | Contenido |
|---|---|
| `Laboratorio 4.docx` | Enunciado del laboratorio |
| `link_base_datos.txt` | Enlace al dataset ESCI (los datos no se suben; el código los descarga) |
| `avance_helsin/ENTREGA_Laboratorio4/Laboratorio4/solucion/` | **Código fuente**: notebook de Colab, paquete `lab4/`, pruebas, `README.md`, `RESULTADOS.md` |
| `avance_helsin/ENTREGA_Laboratorio4/Laboratorio4/work/audios/referencia.wav` | Voz real de referencia para la clonación |
| `avance_helsin/ENTREGA_Laboratorio4/evidencias/` | Resultados y audios de la corrida local de Helsin (RTX 5090, audios de usuario sintéticos) |
| `avance_helsin/ENTREGA_Laboratorio4/LEEME_ENTREGA.md` | Estructura de la entrega y lista de las 20 frases a grabar |
| `khipu/` | Copia de los scripts que están en Khipu (`~/lab4/`) |

No se suben: los datos ESCI, los modelos, los índices ni el archivo con la contraseña de Khipu.

## 2. Diagnóstico frente al enunciado

El diseño y el código cubren todos los requisitos. Lo que falta para poder entregar:

1. **Ejecutar el notebook en Google Colab.** El notebook no tiene salidas y el enunciado exige que el procesamiento corra en Colab. Las cifras de `RESULTADOS.md` son de una máquina local.
2. **Grabar con voz real los 20 turnos de usuario** de los 6 escenarios por voz (lista en `LEEME_ENTREGA.md` §4). Hoy son sintéticos.
3. **Grabar el video** de 20 minutos como máximo (guion en `solucion/README.md` §6).
4. *(Recomendado)* Grabar `otra_voz.wav` con otro integrante, como control de la métrica de semejanza.

Resultados de la corrida local anterior a los cambios de hoy: recuperación nDCG@10 de 0,693 (BM25) a 0,774 (sistema completo); agente 19/22 escenarios; voz 4/6, con fallos en S02 (petición ambigua) y S04 (producto agotado).

## 3. Cambios de código hechos el 24 de noviembre

Probados solo con las pruebas unitarias (83 comprobaciones superadas). Su efecto real sobre el agente se verá en la corrida de Khipu.

| Cambio | Archivo | Para qué |
|---|---|---|
| Cifras en palabras, "2 ×" → "dos unidades de", títulos que no terminan en preposición | `lab4/textutils.py`, `lab4/agent.py` | Mejorar la inteligibilidad de la voz clonada (WER 0,24 con la voz real) |
| Si el usuario ya eligió ("la primera que encuentres") y el LLM solo pregunta, el código le pide una vez que actúe | `lab4/agent.py` (`CHOICE_RE`) | Causa común de los fallos de S02 y S04 |
| El evento de "agotado" se aplica al primer producto mostrado si el carrito está vacío | `lab4/scenarios.py` (`hook_cart_stock`) | Que la situación "producto agotado" se ejercite siempre |
| Pruebas nuevas para lo anterior | `tests/test_unit.py` | |

Advertencia para el informe: los dos cambios del agente se hicieron mirando los mismos escenarios con que se evalúa. `RESULTADOS.md` ya declara ese sesgo; hay que mantener esa nota.

## 4. Qué hay en Khipu

Usuario `diego.perez@khipu.utec.edu.pe`. Todo está en `~/lab4/`:

| Ruta en Khipu | Contenido |
|---|---|
| `~/lab4/Laboratorio4/solucion/` | Código, con los cambios del 24 de noviembre |
| `~/lab4/Laboratorio4/work/` | Datos, índices, audios y resultados que genera la corrida |
| `~/lab4/hf_cache/`, `~/lab4/tts_cache/` | Modelos descargados (unos 25 GB) |
| `~/venvs/lab4/` | Entorno Python 3.11 con torch 2.8.0+cu126 y transformers 4.57.6 |
| `~/lab4/env.sh` | Variables y módulos; se carga con `source` |
| `~/lab4/install.sh`, `prefetch.py`, `prefetch.sh` | Instalación y descargas (los nodos de cómputo no tienen internet, se descarga en el nodo de login) |
| `~/lab4/run_all.sbatch` | Trabajo de Slurm con la tubería completa |
| `~/lab4/logs/` | Registros: `install.log`, `prefetch.log`, `lab4_<jobid>.log`, `etapa_<nombre>_<jobid>.log` |

**Estado al cerrar esta sesión (24 de noviembre, noche):** entorno instalado; ESCI y los seis modelos descargados (22 GB). El **trabajo 65210 está en cola, sin arrancar** (estado `PD`, motivo `Resources`). **Todavía no hay resultados.**

El trabajo pide una A100 completa (40 GB), 8 CPU, 48 GB de RAM y 8 horas. Ejecuta las pruebas unitarias y luego cuatro etapas con `tests/run_local.py`: `data`, `retrieval`, `scenarios` y `voice`.

Sobre la cola: las GPUs están ocupadas por otros usuarios. La estimación de Slurm para la A100 completa era **como muy tarde las 11:20 del 25 de noviembre**; puede arrancar antes si el trabajo que la ocupa termina pronto. Primero se pidió la porción de 20 GB (trabajo 65203, cancelado), pero su inicio estimado era el 25 por la tarde o después. No se usaron "shards" porque no reservan memoria y la tubería necesita unos 18 GB: podría tumbar trabajos de otros usuarios.

### Cómo revisar el avance desde otra máquina

La llave SSH quedó solo en la máquina original, así que desde otra PC se entra con la contraseña (o se instala una llave nueva con `ssh-copy-id`).

```bash
ssh diego.perez@khipu.utec.edu.pe
cd ~/lab4
tail -5 logs/prefetch.log          # debe terminar en PREFETCH_OK y "Submitted batch job N"
squeue -u $USER                    # trabajo en cola (PD) o corriendo (R)
tail -50 logs/lab4_*.log           # salida general del trabajo
grep "termino con codigo" logs/lab4_*.log   # una línea por etapa; 0 = bien
ls Laboratorio4/work/results/      # métricas, gráficos y json de escenarios
```

Si el trabajo no se envió (por ejemplo, falló la descarga de XTTS):

```bash
cd ~/lab4 && source env.sh && python ~/lab4/prefetch.py && cd ~/lab4 && sbatch run_all.sbatch
```

Para repetir solo algunas etapas: `LAB4_STAGES="scenarios voice" sbatch --export=ALL run_all.sbatch`.

### Problemas previsibles

- **Si la A100 tarda demasiado**: probar otra GPU con `sbatch --test-only --gres=gpu:rtxa6000:1 run_all.sbatch`, que solo muestra la hora estimada, y cambiar la línea `#SBATCH --gres=` si conviene.
- **El trabajo queda mucho tiempo en cola**: `squeue -u $USER --start` muestra la hora estimada de inicio.
- **Khipu corta la conexión** si se abren muchas sesiones SSH seguidas; esperar unos minutos.
- Los turnos de usuario de esta corrida son **sintéticos**; la referencia de la clonación sí es la voz real.

## 5. Siguientes pasos

1. Revisar los resultados de Khipu: ¿pasan S02 y S04? ¿baja la WER de la voz clonada? ¿cabe en memoria?
2. Traer los resultados y actualizar `RESULTADOS.md` y el análisis del `README.md` si las cifras cambian:
   `scp -r diego.perez@khipu.utec.edu.pe:~/lab4/Laboratorio4/work/results ./resultados_khipu`
3. Grabar los 20 turnos reales y `otra_voz.wav`.
4. Subir `Laboratorio4/` a Google Drive y **ejecutar el notebook completo en Colab (GPU T4)**; descargar el notebook con salidas y el `RESULTADOS.md` que genera.
5. Grabar el video con la demostración en vivo (celda §12 del notebook).
6. Entregar: carpeta `solucion/` con el notebook ejecutado, evidencias de la corrida de Colab (o enlace a Drive) y el video.

Khipu sirve para validar el código y los cambios, pero no reemplaza la ejecución en Colab que pide el enunciado, salvo que el profesor lo autorice.

## 6. Preparar otra máquina

```bash
git clone https://github.com/diperez-archlnx/msdsia-shopping_assistants_deep_learning.git
cd msdsia-shopping_assistants_deep_learning/avance_helsin/ENTREGA_Laboratorio4/Laboratorio4/solucion
pip install pandas numpy scipy nltk          # suficiente para las pruebas sin GPU
python tests/test_unit.py                    # debe imprimir "83 comprobaciones superadas"
```

La tubería completa necesita una GPU de al menos 16 GB; en una de 8 GB solo cabe la parte de recuperación.
