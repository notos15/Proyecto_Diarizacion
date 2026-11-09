import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import diarizacion as d


class DiarizacionTests(unittest.TestCase):
    def test_cero_una_y_dos_voces(self):
        self.assertEqual(d.estimar_num_hablantes([]), 0)
        self.assertEqual(d.estimar_num_hablantes([[1, 0]]), 1)
        self.assertEqual(d.estimar_num_hablantes([[1, 0], [0.99, 0.01]]), 1)
        self.assertEqual(d.estimar_num_hablantes([[1, 0], [0, 1]]), 2)

    def test_tres_voces_y_limite(self):
        x = np.repeat(np.eye(3), 3, axis=0)
        self.assertEqual(d.estimar_num_hablantes(x), 3)
        self.assertEqual(d.estimar_num_hablantes(x, max_speakers=2), 2)
        self.assertEqual(len(set(d._agrupar(x, num_speakers=2))), 2)

    def test_validaciones(self):
        for kwargs in ({'max_speakers': 0}, {'num_speakers': 6}, {'umbral_distancia': float('nan')}):
            with self.assertRaises(ValueError):
                d._agrupar([[1, 0]], **kwargs)
        with self.assertRaises(ValueError):
            d._agrupar([[0, 0]])
        with self.assertRaises(ValueError):
            d._agrupar([[1, 0]], num_speakers=2)

    def test_ventanas_no_duplican_tiempo(self):
        for longitud in (3840, 25600, 26000, 90000):
            ventanas = d._ventanas(16000, 16000 + longitud)
            self.assertEqual(sum(b - a for _, _, a, b in ventanas), longitud)
            self.assertEqual(ventanas[0][2], 16000)
            self.assertEqual(ventanas[-1][3], 16000 + longitud)
            for anterior, siguiente in zip(ventanas, ventanas[1:]):
                self.assertEqual(anterior[3], siguiente[2])

    def test_reporte_silencios_y_orden(self):
        reporte = d._reporte('ejemplo', 10, [(1, 2), (2, 3), (5, 7)], [8, 8, 2], [])
        self.assertEqual(reporte['tiempo_total_voz_seg'], 4)
        self.assertEqual(reporte['tiempo_silencio_seg'], 6)
        self.assertEqual(reporte['hablantes_detectados'], 2)
        self.assertEqual(reporte['hablantes']['Hablante 1']['porcentaje'], 50)
        self.assertEqual(len(reporte['segmentos']), 2)
        self.assertEqual(reporte['segmentos'][0]['fin'], 3)

    def test_reporte_estadisticas_turnos_y_pausas(self):
        reporte = d._reporte('ejemplo', 10, [(1, 2), (2, 3), (5, 7), (8, 9)], [8, 8, 2, 8], [])
        h1, h2 = reporte['hablantes']['Hablante 1'], reporte['hablantes']['Hablante 2']
        self.assertEqual((h1['turnos'], h1['turno_mas_largo_seg'], h1['primera_intervencion_seg'], h1['ultima_intervencion_seg']), (2, 2, 1, 9))
        self.assertEqual((h2['turnos'], h2['porcentaje_archivo']), (1, 20))
        resumen = reporte['resumen']
        self.assertEqual((resumen['turnos_totales'], resumen['cambios_de_hablante'], resumen['hablante_principal']), (3, 2, 'Hablante 1'))
        self.assertEqual(resumen['pausa_mas_larga'], dict(inicio=3, fin=5, duracion_seg=2, despues_de='Hablante 1', antes_de='Hablante 2'))
        self.assertEqual(resumen['turno_mas_largo']['duracion_seg'], 2)
        self.assertEqual(reporte['transiciones'], {'Hablante 1': {'Hablante 1': 0, 'Hablante 2': 1},
                                                   'Hablante 2': {'Hablante 1': 1, 'Hablante 2': 0}})
        self.assertAlmostEqual(resumen['equilibrio_participacion'], 97.1, places=1)
        linea = reporte['linea_tiempo']
        self.assertEqual(linea['paso_seg'], 1)
        self.assertEqual(len(linea['tramos']), 10)
        self.assertEqual(linea['tramos'][1]['hablantes'], {'Hablante 1': 1})
        self.assertEqual(linea['tramos'][4]['hablantes'], {})
        self.assertAlmostEqual(sum(sum(t['hablantes'].values()) for t in linea['tramos']), 5)

    def test_linea_tiempo_agrupa_audios_largos(self):
        reporte = d._reporte('largo', 3600, [(0, 1799.5), (1800, 3600)], [0, 1], [])
        self.assertEqual(reporte['linea_tiempo']['paso_seg'], 60)
        self.assertEqual(len(reporte['linea_tiempo']['tramos']), 60)
        self.assertEqual(reporte['linea_tiempo']['tramos'][29]['hablantes'], {'Hablante 1': 59.5})
        self.assertEqual(reporte['resumen']['pausas_entre_turnos'], 1)

    def test_envolvente_normalizada(self):
        envolvente = d._envolvente(np.r_[np.zeros(1600), np.ones(1600) * .5, np.ones(1600)], puntos=3)
        self.assertEqual(envolvente['valores'], [0, .5, 1])
        self.assertEqual(envolvente['paso_seg'], .1)
        self.assertEqual(d._envolvente(np.zeros(0)), {'paso_seg': 0.0, 'valores': []})

    def test_audio_silencioso_sin_cargar_modelo(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / 'silencio.wav'
            sf.write(ruta, np.zeros(32000), 16000)
            with patch.object(d, '_encoder') as encoder:
                reporte = d.ejecutar_diarizacion(ruta)
            encoder.assert_not_called()
        self.assertEqual(reporte['hablantes_detectados'], 0)
        self.assertEqual(reporte['tiempo_silencio_seg'], 2)
        self.assertEqual(reporte['resumen']['turnos_totales'], 0)
        self.assertEqual(len(reporte['envolvente']['valores']), 400)
        self.assertEqual(reporte['deteccion_voz']['tiempo_sin_voz_seg'], 2)

    def test_integracion_con_silencio_intermedio(self):
        with tempfile.TemporaryDirectory() as tmp:
            ruta = Path(tmp) / 'voz.wav'
            sf.write(ruta, np.ones(80000) * 0.1, 16000)
            with patch.object(d, '_intervalos_voz', return_value=[(0, 25600), (48000, 80000)]), patch.object(d, '_encoder') as encoder:
                encoder.return_value.embed_utterance.side_effect = [np.array([1., 0.]), np.array([0., 1.])]
                reporte = d.ejecutar_diarizacion(ruta)
        self.assertEqual(reporte['hablantes_detectados'], 2)
        self.assertEqual(reporte['tiempo_total_voz_seg'], 3.6)
        self.assertEqual(reporte['tiempo_silencio_seg'], 1.4)
        self.assertEqual(reporte['segmentos'][1]['inicio'], 3)
        diagnostico = reporte['diagnostico_conteo']
        self.assertEqual(diagnostico['distancias_entre_hablantes']['Hablante 1']['Hablante 2'], 1.0)
        self.assertEqual((diagnostico['huellas_extraidas'], diagnostico['huellas_fiables']), (2, 2))
        self.assertEqual(reporte['deteccion_voz'], dict(regiones_detectadas=2, contextos_utilizados=2,
            tiempo_voz_detectada_seg=3.6, tiempo_voz_descartada_seg=0.0, tiempo_sin_voz_seg=1.4))
        self.assertEqual(reporte['resumen']['cambios_de_hablante'], 1)

    def test_fragmentos_breves_no_crean_personas(self):
        x = np.array([[1, 0, 0], [0.99, 0.01, 0], [0, 1, 0],
                      [0.01, 0.99, 0], [0.1, 0.1, 1]])
        etiquetas = d._agrupar(x, duraciones_contexto=[1.6] * 4 + [0.3])
        self.assertEqual(len(set(etiquetas)), 2)

    def test_una_voz_con_variaciones(self):
        x = np.array([[1, v, 0.1] for v in np.linspace(-0.3, 0.3, 20)])
        self.assertEqual(d.estimar_num_hablantes(x), 1)

    def test_cuatro_voces_no_hay_dos_fijos(self):
        x = np.repeat(np.eye(4), 4, axis=0)
        self.assertEqual(d.estimar_num_hablantes(x), 4)

    def test_duraciones_invalidas(self):
        for duraciones in ([1], [1, -1], [1, float('nan')]):
            with self.assertRaises(ValueError):
                d._agrupar([[1, 0], [0, 1]], duraciones_contexto=duraciones)

    def test_doce_voces_sin_limite_de_cinco(self):
        x = np.repeat(np.eye(12), 4, axis=0)
        self.assertEqual(d.estimar_num_hablantes(x), 12)

    def test_muchas_ventanas_acotan_referencias(self):
        x = np.tile(np.repeat(np.eye(3), 4, axis=0), (100, 1))
        diagnostico = {}
        etiquetas = d._agrupar(x, diagnostico=diagnostico)
        self.assertEqual(len(set(etiquetas)), 3)
        self.assertEqual(len(etiquetas), 1200)
        self.assertEqual(diagnostico['referencias_utilizadas'], d.MAX_REFERENCIAS)

    def test_vad_conserva_ultimo_marco_incompleto(self):
        with patch.object(d.webrtcvad, 'Vad') as vad:
            vad.return_value.is_speech.return_value = True
            self.assertEqual(d._intervalos_voz(np.ones(500)), [(0, 500)])
            for call in vad.return_value.is_speech.call_args_list:
                self.assertEqual(len(call.args[0]), 960)

    def test_pausas_cortas_mejoran_contexto_sin_sumarse_como_voz(self):
        regiones = [(0, 8000), (9600, 17600), (19200, 27200)]
        with patch.object(d, '_cargar_audio', return_value=np.ones(32000) * .1), \
                patch.object(d, '_intervalos_voz', return_value=regiones), \
                patch.object(d, '_encoder') as encoder:
            encoder.return_value.embed_utterance.return_value = np.array([1., 0.])
            reporte = d.ejecutar_diarizacion('ejemplo.m4a')
        encoder.return_value.embed_utterance.assert_called_once()
        self.assertEqual(reporte['tiempo_total_voz_seg'], 1.5)
        self.assertEqual(reporte['tiempo_silencio_seg'], .5)
        self.assertEqual(len(reporte['segmentos']), 3)

    def test_jerarquico_no_necesita_silueta_para_separar(self):
        x = np.repeat(np.eye(4), 3, axis=0)
        diagnostico = {}
        etiquetas = d._agrupar(x, umbral_distancia=.6, estrategia='jerarquico',
                               diagnostico=diagnostico)
        self.assertEqual(len(set(etiquetas)), 4)
        self.assertEqual(diagnostico['estrategia'], 'jerarquico_promedio_coseno')
        self.assertEqual(len(set(d._agrupar(x, max_speakers=3,
            umbral_distancia=.6, estrategia='jerarquico'))), 3)


if __name__ == '__main__':
    unittest.main()
