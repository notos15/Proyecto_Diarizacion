"""Transcribe los turnos manuales existentes en Tiempo_audios.xlsx a JSON."""

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook


CASOS = [
    ("Audio 1", "turnos", "Hablantes por turnos/Diálogo1_Lengua_Taxi.ogg", "Por turnos", 3, 7, 16),
    ("Audio 2", "turnos", "Hablantes por turnos/Diálogo2_Lengua_Taxi.ogg", "Por turnos", 26, 30, 40),
    ("Audio 3", "turnos", "Hablantes por turnos/Diálogo3_Lengua_Taxi.ogg", "Por turnos", 47, 51, 64),
    ("Audio 4", "turnos", "Hablantes por turnos/Diálogo4_Lengua_Taxi.ogg", "Por turnos", 70, 74, 93),
    ("Audio 5", "voces parecidas", "voces parecidas/40_años_de_FJR_Entrevista_a_Francisco_López_Barrera.ogg", "Voces parecidad", 3, 7, 11),
    ("Audio 6", "voces parecidas", "voces parecidas/Audio_entrevista_Nadia_Heck.wav", "Voces parecidad", 26, 30, 38),
    ("Audio 7", "voces parecidas", "voces parecidas/Entrevista_a_Santiago_Urrutia_del_4_de_noviembre_de_2017.ogg", "Voces parecidad", 45, 49, 61),
    ("Audio 8", "voces parecidas", "voces parecidas/request-costarica-luis-javier.mp3", "Voces parecidad", 66, 70, 82),
]


def importar(planilla: Path, audios_dir: Path) -> dict:
    libro = load_workbook(planilla, data_only=True, read_only=True)
    audios = []
    for nombre, categoria, archivo, hoja, fila_duracion, primero, ultimo in CASOS:
        assert (audios_dir / archivo).is_file(), f"Falta el audio: {archivo}"
        pagina = libro[hoja]
        turnos = []
        for fila in range(primero, ultimo + 1):
            inicio, fin, hablante = (pagina.cell(fila, col).value for col in (7, 8, 9))
            if inicio is None or fin is None:
                continue
            if fin <= inicio:
                continue
            turnos.append({
                "inicio": float(inicio),
                "fin": float(fin),
                "hablante": f"Hablante {int(hablante)}",
            })
        assert turnos, f"Sin turnos manuales: {nombre}"
        duracion = max(int(pagina.cell(fila_duracion, 3).value),
                       max(t["fin"] for t in turnos))
        audios.append({
            "id": nombre,
            "categoria": categoria,
            "archivo": archivo,
            "duracion_referencia_seg": duracion,
            "turnos": turnos,
        })
    return {
        "origen": "Turnos anotados manualmente en Tiempo_audios.xlsx; transcritos sin reescuchar los audios.",
        "precision_anotacion": "Los límites manuales se redondearon a segundos enteros en la planilla.",
        "audios": audios,
    }


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--planilla", type=Path, required=True)
    p.add_argument("--audios-dir", type=Path, required=True)
    p.add_argument("--salida", type=Path, default=Path(__file__).with_name("anotaciones.json"))
    args = p.parse_args()
    args.salida.write_text(
        json.dumps(importar(args.planilla, args.audios_dir), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.salida)
