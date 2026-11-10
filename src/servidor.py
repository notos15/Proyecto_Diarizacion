"""Interfaz HTTP local. Reutiliza el mismo análisis que el menú de consola."""
import os
import re
from pathlib import Path
import tempfile
from threading import Lock

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge

from diarizacion import EXTENSIONES_AUDIO, ejecutar_diarizacion

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / '.env')


def crear_app(config=None):
    app = Flask(__name__, template_folder=str(ROOT / 'web/templates'),
                static_folder=str(ROOT / 'web/static'))
    limite_mb = int(os.getenv('MAX_AUDIO_MB', '200'))
    if limite_mb < 1:
        raise ValueError('MAX_AUDIO_MB debe ser mayor que cero.')
    app.config.update(MAX_CONTENT_LENGTH=limite_mb * 1024 * 1024,
                      MAX_AUDIO_MB=limite_mb)
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    bloqueo = Lock()

    @app.get('/')
    def inicio():
        return render_template('index.html', formatos=','.join(sorted(EXTENSIONES_AUDIO)),
                               max_mb=app.config['MAX_AUDIO_MB'])

    @app.errorhandler(RequestEntityTooLarge)
    def demasiado_grande(_error):
        return jsonify(error=f"El archivo supera el límite de {app.config['MAX_AUDIO_MB']} MB."), 413

    @app.post('/api/diarizar')
    def diarizar():
        archivo = request.files.get('audio')
        if archivo is None or not archivo.filename:
            return jsonify(error='Selecciona un archivo de audio.'), 400
        nombre = archivo.filename.replace('\\', '/').rsplit('/', 1)[-1]
        extension = Path(nombre).suffix.lower()
        if extension not in EXTENSIONES_AUDIO:
            return jsonify(error='Formato no admitido. Selecciona un audio; los videos quedan fuera por ahora.'), 400
        cantidad = request.form.get('num_speakers', '')
        if cantidad and not re.fullmatch(r'[1-9][0-9]*', cantidad):
            return jsonify(error='La cantidad de hablantes debe ser un entero positivo.'), 400
        try:
            num_speakers = int(cantidad) if cantidad else None
        except ValueError:
            return jsonify(error='La cantidad de hablantes debe ser un entero positivo.'), 400
        if not bloqueo.acquire(blocking=False):
            return jsonify(error='Ya hay un análisis en curso. Espera a que termine e inténtalo nuevamente.'), 409
        try:
            # No usar el nombre enviado como ruta, ni escribir en data/.
            with tempfile.TemporaryDirectory(prefix='diarizacion_web_') as carpeta:
                ruta = Path(carpeta) / ('audio' + extension)
                archivo.save(ruta)
                if ruta.stat().st_size == 0:
                    return jsonify(error='El archivo está vacío.'), 400
                reporte = ejecutar_diarizacion(ruta, num_speakers=num_speakers)
                reporte['nombre_archivo'] = nombre
                return jsonify(reporte)
        except (ValueError, OSError) as exc:
            return jsonify(error=str(exc)), 422
        except Exception:
            app.logger.exception('Error durante la diarización')
            return jsonify(error='No se pudo completar el análisis. Revisa la consola del servidor e inténtalo nuevamente.'), 500
        finally:
            bloqueo.release()

    return app


if __name__ == '__main__':
    crear_app().run(host=os.getenv('APP_HOST', '127.0.0.1'),
                    port=int(os.getenv('APP_PORT', '8000')), debug=False, threaded=True)
