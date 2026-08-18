# Diarización de Hablantes

Aplicación web desarrollada en Python que recibe un archivo de audio —por ejemplo, una reunión, una clase o una entrevista— y analiza **quién habló, cuándo habló y cuánto tiempo participó cada persona**.

El proyecto busca trabajar también con **habla simultánea (overlapping speech)** y dejar preparada una arquitectura que, como extensión, permita realizar **separación de fuentes de audio** cuando sea necesario.

> Proyecto desarrollado para el ramo **Acústica Computacional con Python 

---

## ¿Qué problema resuelve?

En una reunión o una clase puede ser difícil reconstruir posteriormente **quién intervino, durante cuánto tiempo y en qué momentos hubo participación simultánea**.

La propuesta utiliza **diarización de hablantes (speaker diarization)**, es decir, la identificación temporal de los distintos hablantes presentes en una grabación.

### Casos de uso

- **Reuniones de trabajo:** analizar la participación de cada integrante y apoyar la elaboración de minutas.
- **Salas de clases:** identificar los segmentos correspondientes al profesor o a distintos alumnos.
- **Entrevistas y podcasts:** separar temporalmente las intervenciones de entrevistadores y entrevistados.
- **Estudios de participación:** calcular segundos y porcentaje de tiempo hablado por cada participante.

---

## Objetivo

Diseñar e implementar una herramienta que, a partir de un audio con múltiples hablantes:

1. detecte los segmentos donde existe voz;
2. identifique y agrupe los segmentos pertenecientes a cada hablante;
3. detecte situaciones de habla simultánea;
4. calcule el tiempo de habla y el porcentaje de participación de cada hablante; y
5. presente los resultados mediante una interfaz web sencilla.

### Alcance importante

**Diarización y separación de fuentes no son exactamente lo mismo.**

- La **diarización** responde principalmente a *“¿quién habló y cuándo?”*.
- La **separación de fuentes** intenta recuperar señales de audio independientes cuando las voces están mezcladas.

Por eso, `pyannote-audio` es una excelente base para la diarización, pero si el objetivo final incluye generar un archivo de audio independiente para cada persona durante el solapamiento, será necesario incorporar además una técnica/modelo de **speech separation**, por ejemplo mediante `SpeechBrain`/SepFormer o `Asteroid`.

---

## ¿Cómo funciona?

```text
Audio (.wav / .mp3)
        │
        ▼
┌─────────────────────────────┐
│ 1. Preprocesamiento / VAD   │
│ 2. Segmentación de voz      │
│ 3. Embeddings de hablante   │
│ 4. Clustering / etiquetado  │
│ 5. Detección de solapamiento│
└─────────────────────────────┘
        │
        ▼
Segmentos por hablante
        │
        ├──► Tiempo hablado
        ├──► % de participación
        └──► Línea de tiempo
```

Si se incorpora separación de fuentes:

```text
Segmentos con overlap
        │
        ▼
Speech Separation
(SepFormer / Asteroid u otro modelo)
        │
        ▼
Fuentes de audio estimadas
```

---

## Stack tecnológico

| Capa | Herramientas | Función |
|---|---|---|
| Diarización | `pyannote-audio` | Segmentación y etiquetado de hablantes |
| Procesamiento | `librosa` | Carga, análisis y espectrogramas |
| VAD | `Silero-VAD` / `webrtcvad` | Detección de actividad de voz |
| Embeddings | `SpeechBrain` / `Resemblyzer` | Representación de características de voz |
| Clustering | `scikit-learn` | Agrupamiento de segmentos similares |
| Separación (extensión) | `SpeechBrain` / `Asteroid` | Separación de fuentes en habla mezclada |
| Backend | `FastAPI` | API para recibir audio y devolver resultados |
| Frontend | `React` o HTML/JS | Carga y visualización de resultados |
| Visualización | `Matplotlib` | Espectrogramas y línea de tiempo |

---

## 📈 Métricas / KPIs

- **DER (Diarization Error Rate):** métrica principal para evaluar la calidad de la diarización.
- **JER (Jaccard Error Rate):** métrica complementaria para evaluar la diarización.
- **Tiempo de habla por persona:** segundos y porcentaje del total.
- **Precisión del VAD:** calidad de la detección de voz frente a silencio/ruido.
- **Tiempo de procesamiento:** tiempo requerido para procesar una determinada duración de audio.
- **Si se implementa separación:** se podrán incorporar métricas específicas de separación, como SI-SNRi.

> La meta `DER < 15–20%` se plantea como hipótesis de trabajo y deberá validarse experimentalmente; no se asume como un resultado garantizado.

---

## Datasets de referencia

- **AMI Meeting Corpus:** reuniones reales con múltiples hablantes; especialmente relevante para este proyecto.
- **VoxCeleb:** útil para tareas relacionadas con reconocimiento/verificación de hablantes.
- **LibriSpeech:** audio de habla principalmente limpia.
- **CALLHOME:** conversaciones telefónicas, incluyendo situaciones con solapamiento.
- **WSJ0Mix / LibriMix:** especialmente útiles si se estudia la separación de fuentes de habla.

Los datasets permiten evaluar el sistema frente a una referencia conocida (*ground truth*) y, si corresponde, realizar experimentos de entrenamiento o fine-tuning.

---

## 🔎 Proyectos open source relacionados

Estos repositorios fueron revisados como referencia para el diseño del proyecto:

1. **pyannote-audio** — base principal para diarización de hablantes. Incluye segmentación, embeddings, clustering y soporte para habla solapada.  
   https://github.com/pyannote/pyannote-audio

2. **WhisperX** — combina reconocimiento de voz, timestamps a nivel de palabra y diarización mediante pyannote. Es especialmente interesante como referencia para una aplicación de análisis de reuniones.  
   https://github.com/m-bain/whisperX

3. **OpenTranscribe** — aplicación web autoalojada que integra transcripción, diarización, detección de solapamiento y una arquitectura web con FastAPI.  
   https://github.com/attevon-llc/OpenTranscribe

4. **SpeechBrain** — toolkit de PyTorch que incluye reconocimiento de hablantes y modelos de separación de habla, entre ellos SepFormer.  
   https://github.com/speechbrain/speechbrain

5. **Asteroid** — toolkit especializado en separación de fuentes de audio y habla, con modelos y recetas reproducibles.  
   https://github.com/asteroid-team/asteroid

### ¿Cuál se parece más a nuestra idea?

- **Más cercano al núcleo de diarización:** `pyannote-audio`.
- **Más cercano a una aplicación de análisis de audio con interfaz:** `OpenTranscribe`.
- **Muy útil como referencia para una aplicación que combina ASR + diarización:** `WhisperX`.
- **Más relevante para separar físicamente voces que se superponen:** `SpeechBrain` / `Asteroid`.

---

## Roadmap

- [ ] Revisar y probar proyectos open source de diarización y separación.
- [ ] Seleccionar el modelo base de diarización.
- [ ] Probar el pipeline con audios de 2 o más hablantes.
- [ ] Implementar VAD y diarización.
- [ ] Calcular tiempo y porcentaje de habla por persona.
- [ ] Implementar detección y visualización de solapamiento.
- [ ] Evaluar con DER/JER y datasets de referencia.
- [ ] Desarrollar backend en Python.
- [ ] Desarrollar interfaz web.
- [ ] Evaluar si se incorpora separación de fuentes para generar audios individuales.
- [ ] Documentar resultados y preparar la presentación final.

---

## Flujo de uso esperado

1. El usuario entra a la aplicación.
2. Sube un archivo `.wav` o `.mp3`.
3. El sistema procesa el audio.
4. Se muestran los hablantes detectados y sus segmentos.
5. Se calcula el tiempo y porcentaje de participación.
6. Se visualiza una línea de tiempo con las intervenciones.
7. Si se implementa separación de fuentes, se podrán descargar las fuentes de audio estimadas.


