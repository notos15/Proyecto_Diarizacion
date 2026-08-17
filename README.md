# Diarización de Hablantes 🎙️

Aplicación web que recibe un audio (reunión, clase, entrevista) y **separa automáticamente las voces de los distintos hablantes**, incluso cuando hablan al mismo tiempo, calculando además **cuánto tiempo habló cada persona**.

Proyecto desarrollado para el ramo Acústica Computacional con Python —

---

## 📌 ¿Qué problema resuelve?

Cuando se graba una reunión o una clase, es difícil saber después *quién dijo qué* y *cuánto participó cada persona*. Este proyecto aplica **diarización de hablantes (speaker diarization)** — la tarea de responder "¿quién habló y cuándo?" — para automatizar ese análisis.

**Casos de uso:**
- 💼 **Reuniones de trabajo** — dejar en claro qué aportó cada participante y cuánto tiempo habló.
- 🏫 **Salas de clases** — aislar la voz del profesor del resto del curso.
- 🎧 **Entrevistas / podcasts** — separar las voces para edición o análisis posterior.
- 📊 **Estudios de participación** — medir de forma objetiva el tiempo de habla de cada integrante de un equipo.

---

## 🎯 Objetivo

Diseñar e implementar una herramienta que, a partir de un audio con múltiples hablantes, **identifique y separe las distintas voces** y **calcule el tiempo de habla de cada persona**, incluso en tramos con habla simultánea (*overlapping speech*).

---

## 🧠 ¿Cómo funciona? (Entrada → Proceso → Salida)

```
            ┌───────────────────────────────────────────────┐
 Audio  ──▶ │ 1. VAD (voz vs. silencio)                      │ ──▶  Segmentos por
 (.wav/     │ 2. Espectrograma / extracción de características│      hablante +
  .mp3)     │ 3. Embeddings de hablante                       │      tiempo hablado
            │ 4. Clustering (agrupar voces similares)         │      por persona
            │ 5. Detección de solapamiento (overlap)          │
            └───────────────────────────────────────────────┘
```

1. **VAD (Voice Activity Detection):** descarta silencios y ruido, quedándose solo con los tramos donde hay voz.
2. **Espectrograma:** representación tiempo-frecuencia del audio (vía STFT), base para extraer características.
3. **Embeddings de hablante:** cada segmento de voz se convierte en un vector numérico que representa a esa voz.
4. **Clustering:** se agrupan los vectores similares, asumiendo que pertenecen al mismo hablante.
5. **Overlap detection:** en los tramos donde hablan dos personas a la vez, se asignan ambas etiquetas.

---

## ❓ Hipótesis

> ¿Es posible, utilizando herramientas de diarización de código abierto (como `pyannote-audio`), separar automáticamente las voces de distintos participantes en una reunión o clase —incluso con habla simultánea— y calcular con precisión aceptable (DER < 15-20%) el tiempo de participación de cada persona?

---

## 🛠️ Stack tecnológico

| Capa | Herramientas |
|---|---|
| Diarización / IA | `pyannote-audio`, `SpeechBrain`, `Resemblyzer` |
| Procesamiento de audio | `librosa`, `webrtcvad` / `Silero-VAD` |
| Clustering | `scikit-learn` |
| Backend | Python — `FastAPI` / `Flask` |
| Frontend | `React` (o HTML/JS simple) |
| Visualización | `Matplotlib` |

---

## 📈 Métricas / KPIs

- **DER (Diarization Error Rate)** — métrica principal del área: % de tiempo mal diarizado (falsas alarmas + hablantes perdidos + confusiones de identidad).
- **JER (Jaccard Error Rate)** — complementa al DER, más equilibrada con hablantes de poco tiempo de habla.
- **Tiempo de habla por persona** — segundos y % del total, mostrado directamente al usuario.
- **Precisión del VAD** — % de aciertos al distinguir voz de silencio/ruido.
- **Tiempo de procesamiento** — segundos por minuto de audio procesado.

---

## 📂 Datasets de referencia

- **AMI Meeting Corpus** — reuniones reales con múltiples hablantes.
- **VoxCeleb** — voces para reconocimiento de hablante.
- **LibriSpeech** — audio limpio en inglés.
- **CALLHOME** — conversaciones telefónicas con solapamiento.

Se usan para **evaluar** el sistema (comparando contra la "verdad" conocida) y opcionalmente para **afinar (fine-tuning)** los modelos.

---

## 🗺️ Roadmap del proyecto

- [ ] Investigar proyectos open source de diarización en GitHub.
- [ ] Seleccionar librería/modelo base (`pyannote-audio`) y probar con audios de ejemplo.
- [ ] Implementar pipeline: VAD → espectrograma/features → embeddings → clustering → etiquetado.
- [ ] Calcular tiempo de habla por persona.
- [ ] Desarrollar backend (API en Python).
- [ ] Desarrollar interfaz web (subida de audio + visualización de resultados).
- [ ] Evaluar el sistema con métricas (DER, JER) sobre datasets de prueba y audios propios.
- [ ] Documentar y preparar la presentación final.

---

## 🚀 Cómo usar (flujo de usuario)

1. Entrar a la página web de la aplicación.
2. Subir un archivo de audio (`.wav` o `.mp3`).
3. El sistema procesa el audio (VAD → diarización → cálculo de tiempos).
4. Visualizar en pantalla los segmentos por hablante, la línea de tiempo y el % de participación de cada uno.
5. (Opcional) Descargar el audio separado por hablante y/o un reporte con las métricas.

---

## 👥 Equipo
Benjamin Rojas y Javier Martinez

