import os
from collections import defaultdict
import numpy as np
import librosa
from resemblyzer import VoiceEncoder, preprocess_wav
from sklearn.cluster import SpectralClustering
from sklearn.metrics import silhouette_score

def estimar_num_hablantes(embeddings, max_speakers=5):
    """
    Evalúa cuál es el número real de hablantes usando Spectral Clustering 
    y Silhouette Score sobre las huellas vocales reales (embeddings).
    """
    n_samples = len(embeddings)
    if n_samples < 2:
        return 1

    best_score = -1
    best_k = 1
    limite_k = min(max_speakers + 1, n_samples)

    for k in range(2, limite_k):
        try:
            clustering = SpectralClustering(n_clusters=k, affinity='cosine', random_state=42)
            labels = clustering.fit_predict(embeddings)
            
            score = silhouette_score(embeddings, labels, metric='cosine')
            
            # Exigimos un umbral alto para evitar dividir la voz de la misma persona
            if score > best_score and score > 0.35:
                best_score = score
                best_k = k
        except Exception:
            break

    return best_k


def ejecutar_diarizacion(audio_path: str, max_speakers: int = 5) -> dict:
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"No se encontró el archivo de audio en la ruta: {audio_path}")

    nombre_archivo = os.path.basename(audio_path)

    # 1. Cargar y preprocesar el audio para Resemblyzer
    wav = preprocess_wav(audio_path)
    duracion_total = len(wav) / 16000 # Resemblyzer remuestrea internamente a 16kHz

    # 2. Cargar el modelo preentrenado de extracción de voz
    encoder = VoiceEncoder()

    # 3. Extraer embeddings por segmentos continuos (ventanas de 1.5s con solapamiento)
    # Esto elimina sobreestimaciones por ruidos o silencios cortos
    rate = 1.5  # Evalúa 1.5 segundos de audio por tramo
    _, continuous_embeddings, wav_splits = encoder.embed_utterance(
        wav, return_partials=True, rate=rate
    )

    if len(continuous_embeddings) == 0:
        return {
            "nombre_archivo": nombre_archivo,
            "duracion_total_archivo_seg": round(duracion_total, 2),
            "tiempo_total_voz_seg": 0,
            "tiempo_silencio_seg": round(duracion_total, 2),
            "hablantes_detectados": 0,
            "hablantes": {}
        }

    # 4. Estimar el número exacto de personas analizando la similitud del timbre
    n_speakers = estimar_num_hablantes(continuous_embeddings, max_speakers=max_speakers)

    # 5. Agrupamiento con Spectral Clustering (método de distancia coseno)
    if n_speakers == 1:
        labels = np.zeros(len(continuous_embeddings), dtype=int)
    else:
        clustering = SpectralClustering(n_clusters=n_speakers, affinity='cosine', random_state=42)
        labels = clustering.fit_predict(continuous_embeddings)

    # 6. Calcular tiempos por persona
    duracion_segmento = duracion_total / len(continuous_embeddings)
    tiempo_por_hablante = defaultdict(float)

    for label in labels:
        speaker_name = f"Hablante {label + 1}"
        tiempo_por_hablante[speaker_name] += duracion_segmento

    tiempo_total_voz = sum(tiempo_por_hablante.values())

    resultados = {
        "nombre_archivo": nombre_archivo,
        "duracion_total_archivo_seg": round(duracion_total, 2),
        "tiempo_total_voz_seg": round(tiempo_total_voz, 2),
        "tiempo_silencio_seg": round(max(0, duracion_total - tiempo_total_voz), 2),
        "hablantes_detectados": n_speakers,
        "hablantes": {}
    }

    for speaker, duracion in sorted(tiempo_por_hablante.items()):
        porcentaje = (duracion / tiempo_total_voz * 100) if tiempo_total_voz > 0 else 0
        resultados["hablantes"][speaker] = {
            "segundos": round(duracion, 2),
            "porcentaje": round(porcentaje, 1)
        }

    return resultados