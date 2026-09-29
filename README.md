# Diarización de hablantes

Proyecto de Acústica Computacional con Python que analiza una grabación para estimar **cuántas voces diferentes hay, cuándo habla cada una y cuánto tiempo participa**.

Incluye una página web local y un menú de consola. El procesamiento se realiza en el equipo, sin enviar los audios a servicios externos.

## Funciones actuales

- Cargar un audio desde la página o seleccionarlo desde la carpeta `data` mediante la consola.
- Detectar los momentos donde hay voz.
- Agrupar fragmentos de voces similares.
- Asignar etiquetas como **Hablante 1**, **Hablante 2**, etc.
- Calcular los segundos y el porcentaje de participación.
- Mostrar los segmentos con sus tiempos de inicio y fin.
- Descargar el reporte en formato JSON desde la página.

## ¿Cómo funciona?

1. **Preparación:** se lee el archivo y se convierte a audio mono de 16 kHz.
2. **Detección de voz:** se localizan los intervalos donde hay habla.
3. **Huellas vocales:** un modelo preentrenado extrae características de pequeños fragmentos.
4. **Agrupamiento:** se comparan las huellas y se agrupan las que parecen pertenecer a la misma persona.
5. **Resultados:** se etiquetan los hablantes y se suman sus tiempos de participación.

Los porcentajes se calculan sobre el **tiempo total de voz atribuida**, no sobre la duración completa del archivo.

## Librerías utilizadas

| Librería o modelo | Función |
|---|---|
| SoundFile y FFmpeg | Leer y decodificar archivos de audio. |
| Librosa | Preparar el audio y ajustar su frecuencia de muestreo. |
| WebRTC VAD | Detectar los intervalos con voz. |
| ERes2Net mediante sherpa-onnx | Extraer las huellas vocales. |
| Scikit-learn | Agrupar las huellas según su similitud. |
| NumPy | Realizar cálculos numéricos sobre audio y huellas. |
| Flask | Servir la página local y recibir solicitudes de análisis. |
| python-dotenv | Cargar la configuración desde `.env`. |

La interfaz utiliza **HTML, CSS y JavaScript**. Resemblyzer está disponible como motor alternativo; ERes2Net es el predeterminado.

## Instalación

Desde la carpeta del proyecto, crea y activa un entorno virtual:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requerimientos.txt
```

Si el entorno `.venv` ya existe, basta con activarlo e instalar las dependencias.

Si todavía no tienes un archivo `.env`, créalo desde el ejemplo:

```bash
cp .env.example .env
```

El modelo ERes2Net se descarga automáticamente la primera vez que se necesita. Esa descarga requiere Internet, pero no una cuenta ni un token. Después se reutiliza la copia local.

## Iniciar la página web

Con el entorno virtual activado:

```bash
python src/servidor.py
```

Abre en tu navegador:

**http://127.0.0.1:8000**

Selecciona o arrastra un audio y pulsa **Diarizar audio**. Al terminar, podrás revisar la participación, los segmentos y las advertencias.

Para detener el servidor, presiona **Ctrl+C** en la terminal.

## Usar el menú de consola

Guarda tus audios en la carpeta `data` y ejecuta:

```bash
python src/menu.py
```

El menú permite elegir un archivo y consultar el conteo estimado y los tiempos de participación.

## Configuración

El archivo `.env` permite ajustar:

```dotenv
APP_HOST=127.0.0.1
APP_PORT=8000
MAX_AUDIO_MB=200
```

Reinicia el servidor después de cambiar estos valores. La configuración predeterminada está pensada para uso local.

## Formatos de audio

Se admiten formatos como WAV, MP3, M4A, OGG, FLAC y AAC, entre otros, según los códecs disponibles.

Los videos, incluido MP4, quedan fuera del alcance actual. La reproducción previa depende de los formatos compatibles con el navegador.

## Limitaciones

- El número de hablantes es una **estimación**.
- Puede confundir voces parecidas o dividir una misma voz en varios grupos.
- Una intervención muy breve puede no distinguirse como una voz diferente.
- No detecta ni separa explícitamente las voces simultáneas.
- No identifica nombres ni transcribe lo que se dice.
- El tiempo mostrado como «sin voz atribuida» puede incluir silencios, ruido y fragmentos descartados.
- Los resultados con los audios de desarrollo no garantizan el mismo rendimiento en otras grabaciones.

El modelo está preentrenado: **el proyecto no lo entrena con los archivos cargados**.

## Organización

```text
Proyecto_Diarizacion/
├── README.md
├── requerimientos.txt
├── .env.example
├── src/
│   ├── diarizacion.py      # Procesamiento y agrupamiento de voces
│   ├── modelo_voz.py       # Descarga y carga de ERes2Net
│   ├── menu.py             # Interfaz de consola
│   └── servidor.py         # Servidor web y API
├── web/
│   ├── templates/
│   │   └── index.html
│   └── static/
│       ├── styles.css
│       └── app.js
├── data/                  # Audios para el menú de consola
├── modelos/               # Modelo descargado
└── tests/                 # Pruebas del proyecto
```

Las cargas de la página se procesan en carpetas temporales y se eliminan al finalizar. No se añaden a `data`.

## Pruebas

Para ejecutar las pruebas:

```bash
python -B -m unittest discover -s tests -v
```

Incluyen comprobaciones de lectura de formatos, agrupamiento, cálculo de tiempos, manejo del modelo y servidor web.

La evaluación de precisión con anotaciones temporales y métricas como DER/JER sigue pendiente.

## Próximos pasos

- Evaluar el sistema con audios independientes y turnos anotados.
- Mejorar la identificación de intervenciones breves y voces similares.
- Incorporar detección de habla simultánea.
- Evaluar la separación de voces superpuestas como una función adicional.

## Apoyo de inteligencia artificial en el desarrollo

Durante el desarrollo se utilizaron **ChatGPT y Gemini** como herramientas de apoyo para la programación de la diarización y la resolución de problemas generales encontrados al programar el proyecto.

Entre los problemas abordados estuvieron las dificultades para distinguir correctamente la cantidad de voces, el tratamiento de intervenciones breves y pausas, la compatibilidad de formatos de audio y los errores de dependencias del entorno de Python.

Este apoyo durante la programación es distinto del modelo ERes2Net que utiliza la aplicación para analizar las voces. ChatGPT y Gemini no forman parte del procesamiento de los audios en la aplicación.
