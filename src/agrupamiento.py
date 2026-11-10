"""Agrupamiento de huellas vocales y conteo de hablantes."""

import numpy as np
from sklearn.cluster import AgglomerativeClustering, KMeans
from sklearn.metrics import silhouette_score

MAX_REFERENCIAS = 512


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
        if diagnostico is not None and num_speakers is not None:
            diagnostico["estrategia"] = "cantidad_fija"
        return np.zeros(len(x), dtype=int)
    if num_speakers is not None:
        if diagnostico is not None:
            diagnostico["estrategia"] = "kmeans_cantidad_fija"
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
    if diagnostico is not None:
        distancias = np.clip(1 - centros @ centros.T, 0, 2)
        diagnostico["distancias_entre_grupos"] = np.round(distancias, 3).tolist()
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
