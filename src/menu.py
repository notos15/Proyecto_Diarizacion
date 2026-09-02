import os
import sys
# Importamos la función desde el archivo vecino diarization.py
from diarizacion import ejecutar_diarizacion

# Ruta a la carpeta data
DATA_DIR = os.path.join("data")

def listar_audios():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    archivos = [f for f in os.listdir(DATA_DIR) if f.lower().endswith(('.wav', '.ogg', '.mp3'))]
    return archivos

def imprimir_resultados(reporte):
    print("\n" + "="*60)
    print(f"  RESULTADOS DE DIARIZACIÓN AUTOMÁTICA DEL AUDIO {reporte['nombre_archivo']}")
    print("="*60)
    print(f"• Duración del archivo: {reporte['duracion_total_archivo_seg']}s")
    print(f"• Tiempo de voz activa: {reporte['tiempo_total_voz_seg']}s")
    print(f"• Tiempo en silencio:   {reporte['tiempo_silencio_seg']}s")
    print(f"• Personas detectadas:  {reporte['hablantes_detectados']}\n")
    
    print("Tiempos de participación por persona:")
    for hablante, datos in reporte["hablantes"].items():
        print(f"  👉 {hablante}: {datos['segundos']}s ({datos['porcentaje']}%)")
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
            reporte = ejecutar_diarizacion(audio_path)
            imprimir_resultados(reporte)
        elif opcion == "3":
            return "seleccionar_audio"
        else:
            print("⚠️ Opción no válida. Intenta de nuevo.")

def seleccionar_y_diarizar():
    while True:
        audios = listar_audios()
        if not audios:
            print("\n⚠️ No se encontraron archivos (.wav, .ogg, .mp3) en la carpeta 'data/'.")
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
            reporte = ejecutar_diarizacion(audio_path)
            imprimir_resultados(reporte)
            
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