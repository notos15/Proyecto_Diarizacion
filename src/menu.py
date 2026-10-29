import os
import sys
from pathlib import Path
from diarizacion import EXTENSIONES_AUDIO, ejecutar_diarizacion

# Ruta a la carpeta data
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

def listar_audios():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # La lista es compartida con diarizacion; el lector valida el contenido.
    archivos = [f for f in os.listdir(DATA_DIR)
                if not f.startswith('.') and (Path(DATA_DIR) / f).is_file()
                and Path(f).suffix.lower() in EXTENSIONES_AUDIO]
    return sorted(archivos, key=str.casefold)

def procesar_archivo(audio_path):
    try:
        reporte = ejecutar_diarizacion(audio_path)
    except (OSError, ValueError) as exc:
        print(f"\n⚠️ {exc}")
        return False
    imprimir_resultados(reporte)
    return True

def imprimir_resultados(reporte):
    print("\n" + "="*60)
    print(f"  RESULTADOS DE DIARIZACIÓN AUTOMÁTICA DEL AUDIO {reporte['nombre_archivo']}")
    print("="*60)
    print(f"• Duración del archivo: {reporte['duracion_total_archivo_seg']}s")
    print(f"• Tiempo de voz activa: {reporte['tiempo_total_voz_seg']}s")
    print(f"• Tiempo sin voz atribuida: {reporte['tiempo_silencio_seg']}s")
    print(f"• Cantidad estimada de hablantes:  {reporte['hablantes_detectados']}\n")
    
    print("Tiempos de participación por persona:")
    for hablante, datos in reporte["hablantes"].items():
        print(f"  👉 {hablante}: {datos['segundos']}s ({datos['porcentaje']}%)")
    for advertencia in reporte.get("advertencias", []):
        print(f"  ⚠️ {advertencia}")
    print("="*60 + "\n")

def menu_post_diarizacion(audio_path):
    while True:
        print("\n--- Opciones posteriores ---")
        print("1. Regresar al menú principal")
        print("2. Volver a diarizar el mismo audio")
        print("3. Escoger otro audio")
        
        opcion = input("Selecciona una opción (1-3): ").strip()
        
        if opcion == "1":
            return "menu_principal"
        elif opcion == "2":
            print("\nProcesando de nuevo...")
            procesar_archivo(audio_path)
        elif opcion == "3":
            return "seleccionar_audio"
        else:
            print("⚠️ Opción no válida. Intenta de nuevo.")

def seleccionar_y_diarizar():
    while True:
        audios = listar_audios()
        if not audios:
            print("\n⚠️ No se encontraron audios compatibles en 'data/' (MP3, M4A, WAV, OGG, FLAC, AAC, etc.).")
            input("Presiona Enter para volver al menú principal...")
            break

        print("\n--- Audios disponibles en carpeta 'data' ---")
        for i, audio in enumerate(audios, start=1):
            print(f"{i}. {audio}")
            
        eleccion = input("\nSelecciona el número del audio a analizar (o '0' para cancelar): ").strip()
        
        if eleccion == "0":
            break
            
        if eleccion.isdigit() and 1 <= int(eleccion) <= len(audios):
            audio_seleccionado = audios[int(eleccion) - 1]
            audio_path = os.path.join(DATA_DIR, audio_seleccionado)
            
            print(f"\nAnalizando {audio_seleccionado}...")
            if not procesar_archivo(audio_path):
                continue
            
            siguiente_accion = menu_post_diarizacion(audio_path)
            if siguiente_accion == "menu_principal":
                break
            elif siguiente_accion == "seleccionar_audio":
                continue
        else:
            print("⚠️ Selección inválida. Por favor ingresa un número de la lista.")

def menu_principal():
    while True:
        print("\n" + "="*40)
        print("    SISTEMA DE DIARIZACIÓN ACÚSTICA")
        print("="*40)
        print("1. Diarización")
        print("2. Salir")
        
        opcion = input("Selecciona una opción (1-2): ").strip()
        
        if opcion == "1":
            seleccionar_y_diarizar()
        elif opcion == "2":
            print("\n¡Hasta luego!")
            sys.exit(0)
        else:
            print("⚠️ Opción inválida. Intenta de nuevo.")

if __name__ == "__main__":
    menu_principal()
