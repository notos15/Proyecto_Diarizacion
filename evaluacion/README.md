# Evaluación por turnos

La referencia contiene 94 turnos anotados manualmente en ocho audios cortos
de `Tiempo_audios.xlsx`. Se transcribió a `anotaciones.json` sin volver a
escuchar los archivos. Los límites de la planilla están redondeados a segundos
enteros. La correspondencia de Audio 1 a Audio 8 con los archivos originales
figura en `anotaciones.json`.

## Ejecutar

Desde la carpeta `Proyecto_Diarizacion`, con el entorno `.venv` instalado:

```bash
.venv/bin/python evaluacion/evaluar.py --audios-dir "data/Audios de prueba"
```

El programa ejecuta la diarización actual y crea:

- `resultados/tabla.csv`: conteo de hablantes, diferencia de segundos y DER.
- `resultados/resumen.json`: los mismos valores y el DER global.
- `resultados/lineas_tiempo.html`: comparación visual de los ocho audios.
- `resultados/lineas_tiempo.json`: versión compacta para la presentación.
- `resultados/predicciones/`: salidas completas del sistema.

Para recalcular solo las métricas con las predicciones guardadas, añade
`--reusar`. Si cambias el sistema, ejecuta sin esa opción.

Para regenerar `anotaciones.json` a partir de la planilla original:

```bash
.venv/bin/python evaluacion/importar_anotaciones.py --planilla Tiempo_audios.xlsx --audios-dir "data/Audios de prueba"
```

## Qué mide

El programa compara a intervalos de 10 ms y empareja las etiquetas de hablante
por máximo solapamiento. Calcula DER como
`(voz omitida + falsa alarma + confusión de hablante) / voz manual`.
No aplica collar de tolerancia. Los tramos manuales se recortan a la duración
real del archivo. Esto afecta ligeramente al Audio 5, cuya anotación llega
hasta 62 s y cuyo archivo dura 61,58 s.

El DER depende de la precisión de la referencia. Dado que los límites manuales
están redondeados a segundos, conviene revisarlos con escucha y marcas más
finas antes de usar estas cifras como comparación definitiva.
