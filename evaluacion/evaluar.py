"""Evalúa turnos manuales frente a la salida real del diarizador.

DER sin collar, en pasos de 10 ms: (voz omitida + falsa alarma + confusión) /
tiempo de voz de referencia. Las etiquetas se emparejan por máximo solapamiento.
"""

import argparse
import csv
import html
import json
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from diarizacion import ejecutar_diarizacion  # noqa: E402

PASO = 0.01
COLORES = {
    "correcto": "#80A84F",
    "omision": "#D35E4A",
    "falsa_alarma": "#E9A448",
    "confusion": "#8758A8",
    "silencio": "#D9DDD2",
}


def etiquetas_por_marco(turnos, duracion):
    cantidad = int(np.ceil(duracion / PASO))
    etiquetas = np.full(cantidad, -1, dtype=np.int32)
    nombres = sorted({t["hablante"] for t in turnos})
    indices = {nombre: i for i, nombre in enumerate(nombres)}
    for turno in turnos:
        inicio = max(0, int(round(turno["inicio"] / PASO)))
        fin = min(cantidad, int(round(turno["fin"] / PASO)))
        if fin > inicio:
            if np.any(etiquetas[inicio:fin] != -1):
                raise ValueError("La referencia contiene turnos solapados; este evaluador espera una voz por instante.")
            etiquetas[inicio:fin] = indices[turno["hablante"]]
    return etiquetas, nombres


def medir(referencia, sistema):
    n_ref = int(referencia.max()) + 1 if np.any(referencia >= 0) else 0
    n_sis = int(sistema.max()) + 1 if np.any(sistema >= 0) else 0
    coincidencias = np.zeros((n_ref, n_sis), dtype=np.int64)
    for r, s in zip(referencia, sistema):
        if r >= 0 and s >= 0:
            coincidencias[r, s] += 1
    asignacion = {}
    if n_ref and n_sis:
        filas, columnas = linear_sum_assignment(-coincidencias)
        asignacion = {int(s): int(r) for r, s in zip(filas, columnas)}
    estado = np.zeros(len(referencia), dtype=np.uint8)
    # 0 silencio/correcto sin voz, 1 correcto, 2 omisión, 3 falsa alarma, 4 confusión.
    estado[(referencia >= 0) & (sistema < 0)] = 2
    estado[(referencia < 0) & (sistema >= 0)] = 3
    ambos = (referencia >= 0) & (sistema >= 0)
    mapeado = np.array([asignacion.get(int(s), -99) for s in sistema], dtype=np.int32)
    estado[ambos & (referencia == mapeado)] = 1
    estado[ambos & (referencia != mapeado)] = 4
    voz_ref = int(np.count_nonzero(referencia >= 0))
    voz_sis = int(np.count_nonzero(sistema >= 0))
    omision, falsa_alarma, confusion = (int(np.count_nonzero(estado == i)) for i in (2, 3, 4))
    return {
        "hablantes_manual": n_ref,
        "hablantes_sistema": n_sis,
        "acierto_numero": n_ref == n_sis,
        "voz_manual_seg": round(voz_ref * PASO, 2),
        "voz_sistema_seg": round(voz_sis * PASO, 2),
        "error_tiempo_seg": round((voz_sis - voz_ref) * PASO, 2),
        "omision_seg": round(omision * PASO, 2),
        "falsa_alarma_seg": round(falsa_alarma * PASO, 2),
        "confusion_seg": round(confusion * PASO, 2),
        "der_pct": round(100 * (omision + falsa_alarma + confusion) / voz_ref, 2) if voz_ref else None,
    }, estado, asignacion


def bloques(valores):
    if not len(valores):
        return
    inicio = 0
    for i in range(1, len(valores) + 1):
        if i == len(valores) or valores[i] != valores[inicio]:
            yield inicio, i, int(valores[inicio])
            inicio = i


def linea_tiempo(referencia, sistema, estado, duracion):
    ancho = 940
    filas = [
        ("Manual", referencia, ["#17372F", "#497367", "#80A84F", "#A7C69C"]),
        ("Sistema", sistema, ["#17372F", "#497367", "#80A84F", "#A7C69C"]),
        ("Evaluación", estado, ["#D9DDD2", "#80A84F", "#D35E4A", "#E9A448", "#8758A8"]),
    ]
    partes = [f'<svg viewBox="0 0 1080 150" role="img" aria-label="Línea de tiempo comparativa">']
    for fila, (etiqueta, valores, paleta) in enumerate(filas):
        y = 12 + fila * 40
        partes.append(f'<text x="0" y="{y+16}" font-size="16" fill="#17372F">{etiqueta}</text>')
        for a, b, valor in bloques(valores):
            if valor < 0:
                color = "#D9DDD2"
            else:
                color = paleta[valor % len(paleta)]
            x = 100 + ancho * a / len(valores)
            w = ancho * (b - a) / len(valores)
            partes.append(f'<rect x="{x:.2f}" y="{y}" width="{max(w, 0.7):.2f}" height="24" fill="{color}"/>')
    for i in range(5):
        x = 100 + ancho * i / 4
        partes.append(f'<text x="{x:.1f}" y="145" font-size="13" text-anchor="middle" fill="#36584D">{duracion*i/4:.0f} s</text>')
    partes.append("</svg>")
    return "".join(partes)


def compactar_linea(referencia, sistema, estado, asignacion, duracion):
    """Datos reducidos a intervalos de 0,25 s para una diapositiva editable."""
    ancho = 25
    etiquetas_sistema = np.array([asignacion.get(int(s), 9) if s >= 0 else -1
                                  for s in sistema], dtype=np.int32)
    def resumir(valores):
        celdas = []
        for inicio in range(0, len(valores), ancho):
            bloque = valores[inicio:inicio + ancho]
            opciones, cantidades = np.unique(bloque, return_counts=True)
            celdas.append(int(opciones[np.argmax(cantidades)]))
        return [{"inicio": round(a * ancho * PASO, 2),
                 "fin": round(min(b * ancho * PASO, duracion), 2),
                 "valor": valor}
                for a, b, valor in bloques(np.array(celdas, dtype=np.int32))]
    return {"duracion": duracion, "manual": resumir(referencia),
            "sistema": resumir(etiquetas_sistema), "evaluacion": resumir(estado)}


def evaluar_casos(anotaciones, audios_dir, salida, reusar=False):
    salida.mkdir(parents=True, exist_ok=True)
    pred_dir = salida / "predicciones"
    pred_dir.mkdir(exist_ok=True)
    resultados, graficos, lineas_compactas = [], [], {}
    for caso in anotaciones["audios"]:
        audio = audios_dir / caso["archivo"]
        if not audio.is_file():
            raise FileNotFoundError(audio)
        destino = pred_dir / (caso["id"].lower().replace(" ", "_") + ".json")
        if reusar and destino.exists():
            reporte = json.loads(destino.read_text(encoding="utf-8"))
        else:
            print(f"Procesando {caso['id']}: {audio.name}", flush=True)
            reporte = ejecutar_diarizacion(str(audio))
            destino.write_text(json.dumps(reporte, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        duracion = reporte["duracion_total_archivo_seg"]
        ref, _ = etiquetas_por_marco(caso["turnos"], duracion)
        sis, _ = etiquetas_por_marco(reporte["segmentos"], duracion)
        medidas, estados, asignacion = medir(ref, sis)
        fila = {"audio": caso["id"], "categoria": caso["categoria"], **medidas}
        resultados.append(fila)
        graficos.append((caso["id"], fila, linea_tiempo(ref, sis, estados, duracion)))
        lineas_compactas[caso["id"]] = compactar_linea(ref, sis, estados, asignacion, duracion)
    campos = list(resultados[0])
    with (salida / "tabla.csv").open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        escritor.writeheader()
        escritor.writerows(resultados)
    resumen = {
        "metodo": "DER sin collar, marcos de 10 ms, asignación óptima de etiquetas; anotaciones manuales redondeadas a segundos.",
        "audios": resultados,
        "aciertos_numero": sum(x["acierto_numero"] for x in resultados),
        "total": len(resultados),
        "der_global_pct": round(100 * sum(x["omision_seg"] + x["falsa_alarma_seg"] + x["confusion_seg"] for x in resultados) /
                                sum(x["voz_manual_seg"] for x in resultados), 2),
    }
    (salida / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (salida / "lineas_tiempo.json").write_text(
        json.dumps(lineas_compactas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    partes = ['<!doctype html><html lang="es"><meta charset="utf-8"><title>Evaluación de diarización</title>',
              '<style>body{font:18px Arial;background:#F4F3E9;color:#17372F;max-width:1100px;margin:45px auto;padding:0 25px}h1{font-size:42px}section{margin:45px 0}table{border-collapse:collapse;width:100%}td,th{border-bottom:1px solid #B8C8B8;padding:9px;text-align:left}svg{width:100%;height:auto}.nota{color:#36584D}small{font-size:14px}</style>',
              '<h1>Evaluación por turnos</h1><p class="nota">Referencia manual de la planilla. DER sin collar, a 10 ms. Límites manuales redondeados a segundos.</p>',
              '<p>Colores de evaluación: <span style="color:#80A84F">correcto</span>, <span style="color:#D35E4A">omisión</span>, <span style="color:#E9A448">falsa alarma</span>, <span style="color:#8758A8">confusión de voz</span>.</p>',
              '<table><tr><th>Audio</th><th>Voces manual / sistema</th><th>Error de voz</th><th>DER</th></tr>']
    for x in resultados:
        partes.append(f'<tr><td>{html.escape(x["audio"])}</td><td>{x["hablantes_manual"]} / {x["hablantes_sistema"]}</td><td>{x["error_tiempo_seg"]:+.2f} s</td><td>{x["der_pct"]:.2f} %</td></tr>')
    partes.append('</table>')
    for nombre, fila, svg in graficos:
        partes.append(f'<section><h2>{html.escape(nombre)}</h2>{svg}<small>DER {fila["der_pct"]:.2f} %; voz omitida {fila["omision_seg"]:.2f} s; falsa alarma {fila["falsa_alarma_seg"]:.2f} s; confusión {fila["confusion_seg"]:.2f} s.</small></section>')
    partes.append('</html>')
    (salida / "lineas_tiempo.html").write_text("".join(partes), encoding="utf-8")
    return resumen


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--anotaciones", type=Path, default=Path(__file__).with_name("anotaciones.json"))
    p.add_argument("--audios-dir", type=Path, required=True)
    p.add_argument("--salida", type=Path, default=Path(__file__).with_name("resultados"))
    p.add_argument("--reusar", action="store_true", help="Utiliza predicciones ya guardadas.")
    args = p.parse_args()
    datos = json.loads(args.anotaciones.read_text(encoding="utf-8"))
    print(json.dumps(evaluar_casos(datos, args.audios_dir, args.salida, args.reusar), ensure_ascii=False, indent=2))
