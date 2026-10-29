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
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import silhouette_score

SAMPLE_RATE = 16000
FRAME_SAMPLES = 480  # WebRTC admite marcos de 30 ms a 16 kHz.
MAX_REFERENCIAS = 512  # Acota el coste del conteo en grabaciones largas.
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


def _entero_positivo(valor, nombre):
    if isinstance(valor, bool) or not isinstance(valor, (int, np.integer)) or valor < 1:
        raise ValueError(f"{nombre} debe ser un entero positivo.")


def _agrupar(embeddings, max_speakers=None, umbral_distancia=0.15,
             num_speakers=None, duraciones_contexto=None, diagnostico=None,
             estrategia="silueta"):
    """Estimar grupos con evidencia repetida y asignar después las voces breves.

    El umbral filtra fusiones candidatas en la estrategia jerárquica; en la
    estrategia por silueta filtra la separación entre centros. Silhouette no
    es una probabilidad. Una pausa no reinicia las identidades del archivo.
    """
    if max_speakers is not None:
        _entero_positivo(max_speakers, "max_speakers")
    if not np.isfinite(umbral_distancia) or not 0 < umbral_distancia < 2:
        raise ValueError("umbral_distancia debe estar entre 0 y 2 (exclusivos).")
    if num_speakers is not None:
        _entero_positivo(num_speakers, "num_speakers")
        if max_speakers is not None and num_speakers > max_speakers:
            raise ValueError("num_speakers no puede superar max_speakers.")
    x = np.asarray(embeddings, dtype=float)
    if x.size == 0:
        return np.empty(0, dtype=int)
    if x.ndim != 2 or not np.isfinite(x).all():
        raise ValueError("Los embeddings deben ser una matriz finita.")
    normas = np.linalg.norm(x, axis=1, keepdims=True)
    if np.any(normas <= 1e-12):
        raise ValueError("Se obtuvo una huella vocal nula.")
    x = x / normas
    if num_speakers is not None and num_speakers > len(x):
        raise ValueError("No hay suficientes segmentos para la cantidad indicada.")
    fiables = np.ones(len(x), dtype=bool)
    if duraciones_contexto is not None:
        duraciones = np.asarray(duraciones_contexto, dtype=float)
        if duraciones.shape != (len(x),) or not np.isfinite(duraciones).all() or np.any(duraciones <= 0):
            raise ValueError("Debe haber una duración positiva por embedding.")
        fiables = duraciones >= 1.2
    if len(x) == 1 or num_speakers == 1 or max_speakers == 1:
        return np.zeros(len(x), dtype=int)
    if num_speakers is not None:
        return KMeans(n_clusters=num_speakers, n_init=10, random_state=42).fit_predict(x)

    # Elegir referencias distribuidas por TODO el archivo. Las pausas no
    # reinician el conteo. El resto de las ventanas se asigna posteriormente.
    indices = np.flatnonzero(fiables)
    if len(indices) > MAX_REFERENCIAS:
        indices = indices[np.linspace(0, len(indices) - 1, MAX_REFERENCIAS, dtype=int)]
    y = x[indices]
    if diagnostico is not None:
        diagnostico.update(referencias_totales=int(fiables.sum()),
                           referencias_utilizadas=len(y), candidatos=[])
    if len(y) < 2:
        return np.zeros(len(x), dtype=int)
    # Presupuesto de candidatos para la estrategia anterior por silueta.
    # El árbol jerárquico utiliza directamente las referencias seleccionadas.
    distintos = len(np.unique(np.round(y, 6), axis=0))
    limite = min(distintos, max(1, len(y) // 2))
    if max_speakers is not None:
        limite = min(limite, max_speakers)
    if estrategia == "jerarquico" and len(y) >= 4:
        arbol = AgglomerativeClustering(
            n_clusters=None, distance_threshold=0, metric="cosine", linkage="average"
        ).fit(y)
        # Un corte absoluto puede dividir una voz que cambia de tono. Buscar
        # el mayor salto entre fusiones suficientemente distintas adapta el
        # corte a la dispersión de esta grabación, sin imponer una cantidad.
        distancias_fusion = arbol.distances_
        posibles = np.flatnonzero(distancias_fusion >= umbral_distancia)
        cantidad = 1
        if len(posibles):
            saltos = np.diff(np.r_[0., distancias_fusion])
            corte = int(posibles[np.argmax(saltos[posibles])])
            cantidad = len(y) - corte
            if diagnostico is not None:
                diagnostico["salto_fusion"] = round(float(saltos[corte]), 4)
                anterior = distancias_fusion[corte - 1] if corte else 0.
                diagnostico["corte_adaptado"] = round(float((anterior + distancias_fusion[corte]) / 2), 4)
        if max_speakers is not None:
            cantidad = min(cantidad, max_speakers)
        grupos = (np.zeros(len(y), dtype=int) if cantidad == 1 else
                  AgglomerativeClustering(n_clusters=cantidad, metric="cosine",
                                         linkage="average").fit_predict(y))
    elif len(y) < 4:
        grupos = AgglomerativeClustering(
            n_clusters=None, distance_threshold=umbral_distancia,
            metric="cosine", linkage="average"
        ).fit_predict(y)
        if max_speakers is not None and len(np.unique(grupos)) > max_speakers:
            grupos = KMeans(n_clusters=max_speakers, n_init=10, random_state=42).fit_predict(y)
    else:
        grupos = np.zeros(len(y), dtype=int)
        candidatos = []
        for k in range(2, limite + 1):
            candidato = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(y)
            if np.min(np.bincount(candidato, minlength=k)) < 2:
                continue
            centros = _centros(y, candidato)
            distancias = 1 - centros @ centros.T
            separacion = float(np.min(distancias[np.triu_indices(k, 1)]))
            puntuacion = float(silhouette_score(y, candidato, metric="cosine"))
            if diagnostico is not None:
                diagnostico["candidatos"].append(dict(
                    hablantes=k, silueta=round(puntuacion, 4),
                    separacion=round(separacion, 4)))
            if separacion >= umbral_distancia and puntuacion >= 0.25:
                candidatos.append((puntuacion, candidato))
        if candidatos:
            mejor = max(puntuacion for puntuacion, _ in candidatos)
            puntuacion, grupos = next((puntuacion, candidato)
                                     for puntuacion, candidato in candidatos
                                     if puntuacion >= mejor - 0.08)
            if diagnostico is not None:
                diagnostico["silueta_elegida"] = round(puntuacion, 4)
    if diagnostico is not None and estrategia == "jerarquico":
        cantidad = len(np.unique(grupos))
        diagnostico["estrategia"] = "jerarquico_promedio_coseno"
        diagnostico["umbral_distancia"] = umbral_distancia
        if 1 < cantidad < len(y):
            diagnostico["silueta_elegida"] = round(float(silhouette_score(y, grupos, metric="cosine")), 4)
    centros = _centros(y, grupos)
    # Por lotes: evita una matriz de todas las ventanas por todos los hablantes.
    etiquetas = np.empty(len(x), dtype=int)
    for inicio in range(0, len(x), 2048):
        etiquetas[inicio:inicio + 2048] = np.argmax(x[inicio:inicio + 2048] @ centros.T, axis=1)
    etiquetas[indices] = grupos
    return etiquetas


def _centros(x, etiquetas):
    centros = np.array([x[etiquetas == j].mean(axis=0) for j in np.unique(etiquetas)])
    normas = np.linalg.norm(centros, axis=1, keepdims=True)
    # Los embeddings reales de Resemblyzer son no negativos. Para entradas
    # genéricas opuestas, usar un representante si el promedio se cancela.
    for j in np.flatnonzero(normas[:, 0] <= 1e-12):
        centros[j] = x[etiquetas == np.unique(etiquetas)[j]][0]
    return centros / np.linalg.norm(centros, axis=1, keepdims=True)


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


def _reporte(nombre, duracion, tramos, etiquetas, advertencias):
    nombres, tiempos, segmentos = {}, {}, []
    for (inicio, fin), etiqueta in zip(tramos, etiquetas):
        etiqueta = int(etiqueta)
        if etiqueta not in nombres:
            nombres[etiqueta] = f"Hablante {len(nombres) + 1}"
        hablante = nombres[etiqueta]
        tiempos[hablante] = tiempos.get(hablante, 0.0) + fin - inicio
        if segmentos and segmentos[-1]["hablante"] == hablante and abs(segmentos[-1]["fin"] - inicio) < 1e-8:
            segmentos[-1]["fin"] = fin
        else:
            segmentos.append(dict(inicio=inicio, fin=fin, hablante=hablante))
    voz = sum(tiempos.values())
    return {
        "nombre_archivo": nombre,
        "duracion_total_archivo_seg": round(duracion, 2),
        "tiempo_total_voz_seg": round(voz, 2),
        # Incluye ruido/no voz y detecciones demasiado breves descartadas.
        "tiempo_silencio_seg": round(max(0.0, duracion - voz), 2),
        "hablantes_detectados": len(nombres),
        "hablantes": {
            h: {"segundos": round(t, 2), "porcentaje": round(100 * t / voz, 1)}
            for h, t in tiempos.items()
        },
        "segmentos": [dict(s, inicio=round(s["inicio"], 4), fin=round(s["fin"], 4)) for s in segmentos],
        "metodo": "Huellas vocales + WebRTC VAD + agrupamiento",
        "advertencias": advertencias,
    }


def _contextos_voz(regiones, pausa_maxima=4800):
    """Unir pausas de hasta 0.3 s solo para extraer huellas, no sumar silencio."""
    contextos = []
    for inicio, fin in regiones:
        if contextos and inicio - contextos[-1][1] <= pausa_maxima:
            contextos[-1] = (contextos[-1][0], fin)
        else:
            contextos.append((inicio, fin))
    return contextos


def ejecutar_diarizacion(audio_path: str, max_speakers=None, *,
                         num_speakers=None, umbral_distancia=None,
                         agresividad_vad=0, motor="eres2net") -> dict:
    """Estimar voces sin fijar su número. No separa voces simultáneas.

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
    metodo = ("ERes2Net + WebRTC VAD + agrupamiento jerárquico" if motor == "eres2net"
              else "Resemblyzer + WebRTC VAD + KMeans y selección por silueta")

    def reporte_vacio():
        reporte = _reporte(nombre, duracion, [], [], advertencias)
        reporte["metodo"] = metodo
        reporte["diagnostico_conteo"] = {}
        return reporte

    if len(wav) == 0 or not np.any(wav):
        return reporte_vacio()
    regiones = _intervalos_voz(wav, agresividad_vad)
    # Las pequeñas pausas ya no convierten una frase en fonemas descartados.
    validas = [(a, b) for a, b in _contextos_voz(regiones) if b - a >= 8000]
    if not validas:
        advertencias.append("No se detectó voz utilizable; esto no garantiza ausencia de personas.")
        return reporte_vacio()

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
    reporte = _reporte(nombre, duracion, tramos, etiquetas[indices_tramos], advertencias)
    reporte["metodo"] = metodo
    reporte["diagnostico_conteo"] = diagnostico
    return reporte
