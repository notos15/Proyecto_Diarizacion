"""Resultados, estadísticas y línea de tiempo de la diarización."""

import numpy as np


def _nombres(etiquetas):
    """Asignar «Hablante N» por orden de primera aparición en el archivo."""
    nombres = {}
    for etiqueta in etiquetas:
        etiqueta = int(etiqueta)
        if etiqueta not in nombres:
            nombres[etiqueta] = f"Hablante {len(nombres) + 1}"
    return nombres


def _paso_tramos(duracion, maximo=60):
    """Ancho de tramo (en segundos) para que la línea de tiempo tenga pocos puntos."""
    for paso in (1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600):
        if duracion / paso <= maximo:
            return paso
    return 3600


def _linea_tiempo(duracion, segmentos):
    """Segundos de voz de cada hablante por tramo regular del archivo."""
    if duracion <= 0:
        return {"paso_seg": 1, "tramos": []}
    paso = _paso_tramos(duracion)
    cantidad = int(np.ceil(duracion / paso))
    tramos = [dict(inicio=i * paso, fin=round(min((i + 1) * paso, duracion), 2), hablantes={})
              for i in range(cantidad)]
    for s in segmentos:
        primero = min(int(s["inicio"] // paso), cantidad - 1)
        ultimo = min(int(np.ceil(s["fin"] / paso)), cantidad)
        for i in range(primero, max(ultimo, primero + 1)):
            solapado = min(s["fin"], (i + 1) * paso) - max(s["inicio"], i * paso)
            if solapado > 1e-9:
                voz = tramos[i]["hablantes"]
                voz[s["hablante"]] = voz.get(s["hablante"], 0.0) + solapado
    for tramo in tramos:
        tramo["hablantes"] = {h: round(v, 2) for h, v in tramo["hablantes"].items()}
    return {"paso_seg": paso, "tramos": tramos}


def _estadisticas(duracion, voz, tiempos, segmentos):
    """Resumen de turnos, pausas y alternancia a partir de los segmentos."""
    por_hablante = {}
    for s in segmentos:
        datos = por_hablante.setdefault(s["hablante"], dict(turnos=0, mas_largo=0.0, primera=s["inicio"], ultima=s["fin"]))
        largo = s["fin"] - s["inicio"]
        datos["turnos"] += 1
        datos["mas_largo"] = max(datos["mas_largo"], largo)
        datos["primera"] = min(datos["primera"], s["inicio"])
        datos["ultima"] = max(datos["ultima"], s["fin"])
    hablantes = {}
    for h, t in tiempos.items():
        datos = por_hablante[h]
        hablantes[h] = {
            "segundos": round(t, 2),
            "porcentaje": round(100 * t / voz, 1),
            "porcentaje_archivo": round(100 * t / duracion, 1) if duracion > 0 else 0.0,
            "turnos": datos["turnos"],
            "turno_medio_seg": round(t / datos["turnos"], 2),
            "turno_mas_largo_seg": round(datos["mas_largo"], 2),
            "primera_intervencion_seg": round(datos["primera"], 2),
            "ultima_intervencion_seg": round(datos["ultima"], 2),
        }
    transiciones = {h: {otro: 0 for otro in tiempos} for h in tiempos}
    cambios = 0
    pausas = []
    for anterior, actual in zip(segmentos, segmentos[1:]):
        transiciones[anterior["hablante"]][actual["hablante"]] += 1
        cambios += anterior["hablante"] != actual["hablante"]
        hueco = actual["inicio"] - anterior["fin"]
        if hueco > 1e-9:
            pausas.append(dict(inicio=round(anterior["fin"], 2), fin=round(actual["inicio"], 2),
                               duracion_seg=round(hueco, 2), despues_de=anterior["hablante"],
                               antes_de=actual["hablante"]))
    resumen = {
        "turnos_totales": len(segmentos),
        "cambios_de_hablante": cambios,
        "turno_medio_seg": round(voz / len(segmentos), 2) if segmentos else 0.0,
        "porcentaje_voz_archivo": round(100 * voz / duracion, 1) if duracion > 0 else 0.0,
        "pausas_entre_turnos": len(pausas),
        "pausa_media_seg": round(sum(p["duracion_seg"] for p in pausas) / len(pausas), 2) if pausas else 0.0,
        "hablante_principal": max(tiempos, key=tiempos.get) if tiempos else None,
    }
    if segmentos:
        mayor = max(segmentos, key=lambda s: s["fin"] - s["inicio"])
        resumen["turno_mas_largo"] = dict(hablante=mayor["hablante"], inicio=round(mayor["inicio"], 2),
                                          fin=round(mayor["fin"], 2),
                                          duracion_seg=round(mayor["fin"] - mayor["inicio"], 2))
    if pausas:
        resumen["pausa_mas_larga"] = max(pausas, key=lambda p: p["duracion_seg"])
    if len(tiempos) > 1:
        # Entropía normalizada de las cuotas: 100 = todos hablan lo mismo.
        cuotas = np.array([t / voz for t in tiempos.values()])
        entropia = -float(np.sum(cuotas * np.log(cuotas, where=cuotas > 0, out=np.zeros_like(cuotas))))
        resumen["equilibrio_participacion"] = round(float(100 * entropia / np.log(len(tiempos))), 1)
    return hablantes, resumen, transiciones


def _reporte(nombre, duracion, tramos, etiquetas, advertencias):
    nombres = _nombres(etiquetas)
    tiempos, segmentos = {}, []
    for (inicio, fin), etiqueta in zip(tramos, etiquetas):
        hablante = nombres[int(etiqueta)]
        tiempos[hablante] = tiempos.get(hablante, 0.0) + fin - inicio
        if segmentos and segmentos[-1]["hablante"] == hablante and abs(segmentos[-1]["fin"] - inicio) < 1e-8:
            segmentos[-1]["fin"] = fin
        else:
            segmentos.append(dict(inicio=inicio, fin=fin, hablante=hablante))
    voz = sum(tiempos.values())
    hablantes, resumen, transiciones = _estadisticas(duracion, voz, tiempos, segmentos)
    return {
        "nombre_archivo": nombre,
        "duracion_total_archivo_seg": round(duracion, 2),
        "tiempo_total_voz_seg": round(voz, 2),
        # Incluye ruido/no voz y detecciones demasiado breves descartadas.
        "tiempo_silencio_seg": round(max(0.0, duracion - voz), 2),
        "hablantes_detectados": len(nombres),
        "hablantes": hablantes,
        "resumen": resumen,
        "transiciones": transiciones,
        "linea_tiempo": _linea_tiempo(duracion, segmentos),
        "segmentos": [dict(s, inicio=round(s["inicio"], 4), fin=round(s["fin"], 4)) for s in segmentos],
        "metodo": "Huellas vocales + WebRTC VAD + agrupamiento",
        "advertencias": advertencias,
    }
