"""Contrato JSON, validación de cargas y limpieza de archivos temporales."""
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from servidor import crear_app


class ServidorTests(unittest.TestCase):
    def setUp(self):
        self.app = crear_app({'TESTING': True})
        self.client = self.app.test_client()

    def subir(self, nombre='prueba.m4a', contenido=b'audio', cantidad=None):
        data = {'audio': (io.BytesIO(contenido), nombre)}
        if cantidad is not None:
            data['num_speakers'] = cantidad
        return self.client.post('/api/diarizar', data=data)

    def test_pagina(self):
        r = self.client.get('/')
        self.assertEqual(r.status_code, 200)
        self.assertIn(b'Diarizar audio', r.data)
        self.assertIn(b'.m4a', r.data)
        for marcador in (b'id="player"', b'id="timeline"', b'id="segment-filter"', b'id="diagnostics"',
                         b'id="num-speakers"', b'id="record-panel"', b'id="start-record"',
                         b'id="pause-record"', b'id="stop-record"', b'data-speakers="auto"'):
            self.assertIn(marcador, r.data)
        with self.client.get('/static/app.js') as recurso:
            self.assertEqual(recurso.status_code, 200)
        with self.client.get('/static/resultados.js') as recurso:
            self.assertEqual(recurso.status_code, 200)
        with self.client.get('/static/controles.js') as recurso:
            self.assertEqual(recurso.status_code, 200)

    def test_validaciones(self):
        self.assertEqual(self.client.post('/api/diarizar').status_code, 400)
        self.assertEqual(self.subir('video.mp4').status_code, 400)
        self.assertEqual(self.subir(contenido=b'').status_code, 400)
        self.app.config['MAX_CONTENT_LENGTH'] = 20
        r = self.subir()
        self.assertEqual(r.status_code, 413)
        self.assertIn('error', r.json)

    def test_json_y_limpieza(self):
        rutas = []
        def analizar(ruta, *, num_speakers):
            rutas.append(ruta)
            self.assertIsNone(num_speakers)
            self.assertEqual(ruta.read_bytes(), b'audio')
            return {'hablantes_detectados': 3, 'advertencias': ['Revisar voces'], 'segmentos': []}
        with patch('servidor.ejecutar_diarizacion', side_effect=analizar):
            r = self.subir('../../nombre con acento á.M4A')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json['hablantes_detectados'], 3)
        self.assertEqual(r.json['nombre_archivo'], 'nombre con acento á.M4A')
        self.assertEqual(rutas[0].name, 'audio.m4a')
        self.assertFalse(rutas[0].exists())

    def test_error_limpia_y_permite_otro_analisis(self):
        rutas = []
        def fallar(ruta, *, num_speakers):
            rutas.append(ruta)
            raise ValueError('Audio dañado')
        with patch('servidor.ejecutar_diarizacion', side_effect=fallar):
            for _ in range(2):
                r = self.subir()
                self.assertEqual(r.status_code, 422)
                self.assertEqual(r.json['error'], 'Audio dañado')
        self.assertTrue(all(not ruta.exists() for ruta in rutas))

    def test_evitar_analisis_simultaneos(self):
        def analizar(_ruta, *, num_speakers):
            with self.app.test_client() as otro:
                r = otro.post('/api/diarizar', data={'audio': (io.BytesIO(b'audio'), 'otro.wav')})
                self.assertEqual(r.status_code, 409)
            return {'advertencias': []}
        with patch('servidor.ejecutar_diarizacion', side_effect=analizar):
            self.assertEqual(self.subir().status_code, 200)

    def test_cantidad_opcional_y_validacion(self):
        with patch('servidor.ejecutar_diarizacion', return_value={'advertencias': []}) as analizar:
            self.assertEqual(self.subir(cantidad='3').status_code, 200)
            self.assertEqual(analizar.call_args.kwargs['num_speakers'], 3)
            self.assertEqual(self.subir(cantidad='').status_code, 200)
            self.assertIsNone(analizar.call_args.kwargs['num_speakers'])
            for valor in ('0', '-1', '1.5', 'abc', ' 2', '2 ', '02', '+2'):
                with self.subTest(valor=valor):
                    self.assertEqual(self.subir(cantidad=valor).status_code, 400)
            self.assertEqual(analizar.call_count, 2)
