"""Diarización local con ERes2Net, WebRTC VAD y distancia coseno.

Las etiquetas identifican voces dentro del archivo; no infieren sexo ni género.
Referencias y limitaciones: README.md, sección «Implementación actual».
"""

import os
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

import librosa
import numpy as np
import webrtcvad
import soundfile as sf
from resemblyzer import VoiceEncoder

from agrupamiento import MAX_REFERENCIAS, _agrupar, _centros, _entero_positivo
from reporte import _estadisticas, _linea_tiempo, _nombres, _paso_tramos, _reporte

SAMPLE_RATE = 16000
FRAME_SAMPLES = 480  # WebRTC admite marcos de 30 ms a 16 kHz.
EXTENSIONES_AUDIO = frozenset({
    ".wav", ".wave", ".mp3", ".m4a", ".m4b", ".aac", ".ogg", ".oga",
    ".opus", ".flac", ".aif", ".aiff", ".aifc", ".wma", ".amr",
    ".caf", ".au", ".snd", ".ac3", ".ape", ".alac", ".mka", ".mp2",
    ".aax", ".wv", ".w64", ".dsf", ".dff", ".tta", ".tak",
})
EXTENSIONES_VIDEO = frozenset({
    ".mp4", ".m4v", ".mov", ".mkv", ".avi", ".webm", ".wmv",
    ".flv", ".mpeg", ".mpg", ".ts", ".mts", ".m2ts", ".3gp", ".ogv",
})


class ErrorAudio(ValueError):
    """Archivo sin audio decodificable o lector no disponible."""


def _ffmpeg():
    """Usar FFmpeg instalado o el ejecutable incluido en imageio-ffmpeg."""
    ejecutable = shutil.which("ffmpeg")
    if ejecutable:
        return ejecutable
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except (ImportError, RuntimeError) as exc:
        raise ErrorAudio(
            "Este formato necesita FFmpeg. Instala las dependencias con "
            "'python3 -m pip install -r requerimientos.txt'."
        ) from exc


def _cargar_audio(audio_path):
    """Leer un archivo de audio. Los formatos de video quedan fuera de alcance.

    SoundFile conserva la ruta de lectura existente para WAV/OGG/FLAC/MP3.
    Para otros formatos de audio, FFmpeg decodifica la primera pista a una
    copia temporal mono a 16 kHz. El archivo original no se modifica.
    """
    ruta = Path(audio_path).expanduser().resolve()
    if not ruta.is_file():
        raise FileNotFoundError(f"No se encontró el archivo de audio: {ruta}")
    if ruta.suffix.lower() in EXTENSIONES_VIDEO:
        raise ErrorAudio("Por ahora solo se admiten archivos de audio, no formatos de video.")
    try:
        wav, sr = sf.read(ruta, dtype="float32", always_2d=True)
    except sf.LibsndfileError:
        with tempfile.TemporaryDirectory(prefix="diarizacion_") as carpeta:
            temporal = Path(carpeta) / "audio.wav"
            comando = [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-xerror", "-protocol_whitelist", "file,pipe",
                "-i", str(ruta), "-map", "0:a:0", "-vn", "-sn", "-dn",
                "-ac", "1", "-ar", str(SAMPLE_RATE), "-c:a", "pcm_f32le",
                "-y", str(temporal),
            ]
            try:
                resultado = subprocess.run(comando, capture_output=True, text=True,
                                           errors="replace", check=False)
            except OSError as exc:
                raise ErrorAudio("No se pudo ejecutar FFmpeg para leer este archivo.") from exc
            if resultado.returncode:
                if "matches no streams" in resultado.stderr:
                    raise ErrorAudio(f"'{ruta.name}' no contiene una pista de audio.")
                raise ErrorAudio(
                    f"No se pudo leer '{ruta.name}': el archivo está dañado, "
                    "protegido o su formato/códec no está disponible."
                )
            try:
                wav, sr = sf.read(temporal, dtype="float32", always_2d=True)
            except (OSError, sf.LibsndfileError) as exc:
                raise ErrorAudio("No se pudo leer el audio extraído del archivo.") from exc
    wav = librosa.to_mono(wav.T)
    if len(wav) and sr != SAMPLE_RATE:
        wav = librosa.resample(wav, orig_sr=sr, target_sr=SAMPLE_RATE)
    return wav


def estimar_num_hablantes(embeddings, max_speakers=None, umbral_distancia=0.15):
    """Estimar cantidad de voces; devuelve cero si no hay huellas vocales."""
    return len(np.unique(_agrupar(embeddings, max_speakers, umbral_distancia)))


@lru_cache(maxsize=2)
def _encoder(motor="eres2net"):
    # Reutilizar pesos al analizar otro audio desde el menú.
    if motor == "resemblyzer":
        return VoiceEncoder(verbose=False)
    from modelo_voz import EncoderERes2Net
    return EncoderERes2Net()


def _intervalos_voz(wav, agresividad=2):
    """Devolver intervalos en muestras, sin borrar ni concatenar silencios."""
    vad = webrtcvad.Vad(agresividad)
    pcm = (np.clip(wav, -1, 1) * 32767).astype("<i2")
    intervalos = []
    inicio = None
    for pos in range(0, len(pcm), FRAME_SAMPLES):
        frame = pcm[pos:pos + FRAME_SAMPLES]
        if len(frame) < FRAME_SAMPLES:
            frame = np.pad(frame, (0, FRAME_SAMPLES - len(frame)))
        activo = vad.is_speech(frame.tobytes(), SAMPLE_RATE)
        if activo and inicio is None:
            inicio = pos
        elif not activo and inicio is not None:
            intervalos.append((inicio, pos))
            inicio = None
    if inicio is not None:
        intervalos.append((inicio, len(wav)))
    return intervalos


def _ventanas(inicio, fin, ancho=25600):
    """Contextos solapados y tramos de atribución sin solapamiento."""
    salto = 12800
    comienzos = list(range(inicio, max(inicio, fin - ancho) + 1, salto))
    if fin - inicio > ancho and comienzos[-1] + ancho < fin:
        comienzos.append(fin - ancho)
    contextos = [(p, min(p + ancho, fin)) for p in comienzos]
    centros = [(a + b) // 2 for a, b in contextos]
    bordes = [inicio] + [(a + b) // 2 for a, b in zip(centros, centros[1:])] + [fin]
    return [(a, b, bordes[i], bordes[i + 1]) for i, (a, b) in enumerate(contextos)]


def _envolvente(wav, puntos=400):
    """Nivel RMS normalizado por bloques, para dibujar la forma de onda."""
    if len(wav) == 0:
        return {"paso_seg": 0.0, "valores": []}
    bloque = max(1, int(np.ceil(len(wav) / puntos)))
    cantidad = int(np.ceil(len(wav) / bloque))
    relleno = np.zeros(cantidad * bloque, dtype=np.float32)
    relleno[:len(wav)] = wav
    rms = np.sqrt(np.mean(relleno.reshape(cantidad, bloque) ** 2, axis=1))
    maximo = float(rms.max())
    if maximo > 0:
        rms = rms / maximo
    return {"paso_seg": round(bloque / SAMPLE_RATE, 4),
            "valores": [round(float(v), 3) for v in rms]}


def _contextos_voz(regiones, pausa_maxima=4800):
    """Unir pausas de hasta 0.3 s solo para extraer huellas, no sumar silencio."""
    contextos = []
    for inicio, fin in regiones:
        if contextos and inicio - contextos[-1][1] <= pausa_maxima:
            contextos[-1] = (contextos[-1][0], fin)
        else:
            contextos.append((inicio, fin))
    return contextos


def _resumen_vad(duracion, regiones, validas, voz_atribuida):
    """Cuánta voz detectó el VAD, cuánta se descartó por breve y cuánto es silencio real."""
    detectada = sum(b - a for a, b in regiones) / SAMPLE_RATE
    return {
        "regiones_detectadas": len(regiones),
        "contextos_utilizados": len(validas),
        "tiempo_voz_detectada_seg": round(detectada, 2),
        "tiempo_voz_descartada_seg": round(max(0.0, detectada - voz_atribuida), 2),
        "tiempo_sin_voz_seg": round(max(0.0, duracion - detectada), 2),
    }


def ejecutar_diarizacion(audio_path: str, max_speakers=None, *,
                         num_speakers=None, umbral_distancia=None,
                         agresividad_vad=0, motor="eres2net") -> dict:
    """Agrupar voces con cantidad opcional. No separa voces simultáneas.

    ERes2Net usa agrupamiento jerárquico con corte adaptado (base 0.6). El motor opcional
    resemblyzer conserva la selección por silueta (umbral 0.15).
    Los umbrales pertenecen a espacios de huellas distintos y no son equivalentes.
    """
    if motor not in ("eres2net", "resemblyzer"):
        raise ValueError("motor debe ser 'eres2net' o 'resemblyzer'.")
    if umbral_distancia is None:
        umbral_distancia = 0.6 if motor == "eres2net" else 0.15
    _agrupar([], max_speakers, umbral_distancia, num_speakers)
    if isinstance(agresividad_vad, bool) or not isinstance(agresividad_vad, (int, np.integer)) or agresividad_vad not in range(4):
        raise ValueError("agresividad_vad debe ser un entero entre 0 y 3.")
    wav = _cargar_audio(audio_path)
    if not np.isfinite(wav).all():
        raise ValueError("El audio contiene muestras no finitas.")
    duracion = len(wav) / SAMPLE_RATE
    nombre = os.path.basename(audio_path)
    advertencias = ["Estimación acústica: puede confundir voces parecidas o dividir una misma voz.",
                    "Las voces simultáneas no se identifican por separado."]
    if num_speakers is not None:
        metodo = f"{'ERes2Net' if motor == 'eres2net' else 'Resemblyzer'} + WebRTC VAD + KMeans (cantidad indicada)"
    else:
        metodo = ("ERes2Net + WebRTC VAD + agrupamiento jerárquico" if motor == "eres2net"
                  else "Resemblyzer + WebRTC VAD + KMeans y selección por silueta")

    def reporte_vacio(regiones=()):
        if num_speakers is not None:
            advertencias.append("No se pudo aplicar la cantidad indicada porque no se detectó voz suficiente.")
        reporte = _reporte(nombre, duracion, [], [], advertencias)
        reporte["hablantes_solicitados"] = num_speakers
        reporte["metodo"] = metodo
        reporte["diagnostico_conteo"] = {}
        reporte["envolvente"] = _envolvente(wav)
        reporte["deteccion_voz"] = _resumen_vad(duracion, regiones, [], 0.0)
        return reporte

    if len(wav) == 0 or not np.any(wav):
        return reporte_vacio()
    regiones = _intervalos_voz(wav, agresividad_vad)
    # Las pequeñas pausas ya no convierten una frase en fonemas descartados.
    validas = [(a, b) for a, b in _contextos_voz(regiones) if b - a >= 8000]
    if not validas:
        advertencias.append("No se detectó voz utilizable; esto no garantiza ausencia de personas.")
        return reporte_vacio(regiones)

    embeddings, tramos, indices_tramos, duraciones_contexto = [], [], [], []
    encoder = _encoder(motor)
    indice_region = 0
    for inicio, fin in validas:
        for a, b, t0, t1 in _ventanas(inicio, fin, 51200 if motor == "eres2net" else 25600):
            fragmento = wav[a:b].copy()
            rms = float(np.sqrt(np.mean(fragmento ** 2)))
            if rms > 1e-8:
                fragmento = np.clip(fragmento * min(10.0, 0.0316 / rms), -1, 1)
            indice_huella = len(embeddings)
            embeddings.append(encoder.embed_utterance(fragmento))
            duraciones_contexto.append((b - a) / SAMPLE_RATE)
            # Intersecar atribuciones con el VAD original: las pausas usadas
            # como contexto no se contabilizan como tiempo hablado.
            while indice_region < len(regiones) and regiones[indice_region][1] <= t0:
                indice_region += 1
            j = indice_region
            while j < len(regiones) and regiones[j][0] < t1:
                desde, hasta = max(t0, regiones[j][0]), min(t1, regiones[j][1])
                if hasta > desde:
                    tramos.append((desde / SAMPLE_RATE, hasta / SAMPLE_RATE))
                    indices_tramos.append(indice_huella)
                j += 1
    diagnostico = {}
    etiquetas = _agrupar(embeddings, max_speakers, umbral_distancia, num_speakers,
                         duraciones_contexto=duraciones_contexto, diagnostico=diagnostico,
                         estrategia="jerarquico" if motor == "eres2net" else "silueta")
    if diagnostico.get("referencias_totales", 0) > MAX_REFERENCIAS:
        advertencias.append("Conteo estimado con referencias distribuidas por todo el audio; intervenciones poco frecuentes pueden quedar fuera de la muestra.")
    if diagnostico.get("silueta_elegida", 1) < 0.35:
        advertencias.append("La separación de voces es débil: conviene revisar el conteo y los turnos.")
    if num_speakers is None and len(np.unique(etiquetas)) == max_speakers:
        advertencias.append("Se alcanzó max_speakers; aumenta el límite si esperas más personas.")
    if num_speakers is None and sum(t >= 1.2 for t in duraciones_contexto) < 4:
        advertencias.append("Hay pocas referencias largas: el conteo tiene evidencia insuficiente.")
    if any(t < 1.2 for t in duraciones_contexto):
        advertencias.append("Las intervenciones breves se asignan a las voces de referencia; una persona que solo habla brevemente puede no distinguirse.")
    if num_speakers is None and len(np.unique(etiquetas)) == 1:
        advertencias.append("Solo se distinguió un grupo de voz; esto no confirma que haya una sola persona.")
    if num_speakers is not None and len(np.unique(etiquetas)) != num_speakers:
        advertencias.append("No se pudieron distinguir todas las voces indicadas con las huellas disponibles.")
    reporte = _reporte(nombre, duracion, tramos, etiquetas[indices_tramos], advertencias)
    reporte["hablantes_solicitados"] = num_speakers
    reporte["metodo"] = metodo
    if "distancias_entre_grupos" in diagnostico:
        nombres = _nombres(etiquetas[indices_tramos])
        matriz = diagnostico.pop("distancias_entre_grupos")
        diagnostico["distancias_entre_hablantes"] = {
            nombres[a]: {nombres[b]: matriz[a][b] for b in nombres if b < len(matriz)}
            for a in nombres if a < len(matriz)}
    diagnostico["huellas_extraidas"] = len(embeddings)
    diagnostico["huellas_fiables"] = int(sum(t >= 1.2 for t in duraciones_contexto))
    reporte["diagnostico_conteo"] = diagnostico
    reporte["envolvente"] = _envolvente(wav)
    reporte["deteccion_voz"] = _resumen_vad(duracion, regiones, validas, reporte["tiempo_total_voz_seg"])
    return reporte
