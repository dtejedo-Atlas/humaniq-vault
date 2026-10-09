"""Genera CVs sintéticos únicos en PDF para pruebas de lote (sin tocar CVs reales)."""
import os
import sys
import uuid

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

OUT = sys.argv[1] if len(sys.argv) > 1 else '/tmp/cvs_e2e'
COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 6
WITH_HISTORY = os.environ.get('WITH_HISTORY', '1') == '1'

NAMES = ['Lucía Marín Ocampo', 'Fernando Beltrán Ríos', 'Paula Quiroga Serna', 'Néstor Ibarra Vela',
         'Mariela Cossío Duarte', 'Aarón Peláez Mondragón', 'Silvia Rentería Luna', 'Óscar Dávila Pinto']

os.makedirs(OUT, exist_ok=True)
paths = []
for index in range(COUNT):
    tag = uuid.uuid4().hex[:8]
    name = f'{NAMES[index % len(NAMES)]} {tag.upper()}'
    path = os.path.join(OUT, f'cv_e2e_{tag}.pdf')
    pdf = canvas.Canvas(path, pagesize=LETTER)
    y = 740
    lines = [
        name,
        f'Correo: qa.{tag}@humaniq-test.mx  |  Teléfono: +52 55 {1000 + index:04d} {2000 + index:04d}',
        'Ciudad de México, México',
        '',
        'RESUMEN PROFESIONAL',
        'Directora Comercial con 12 años de experiencia en telecomunicaciones y servicios B2B,',
        'liderando equipos de venta consultiva y cuentas estratégicas en México y Centroamérica.',
        '',
    ]
    if WITH_HISTORY:
        lines += [
            'EXPERIENCIA PROFESIONAL',
            'Directora Comercial — Telered Comunicaciones S.A. de C.V.',
            'Enero 2021 - Actualidad. Operador de telecomunicaciones fijas y móviles.',
            'Responsable de 180 MDP de ingreso anual y de un equipo de 24 ejecutivos.',
            '',
            'Gerente de Cuentas Estratégicas — Grupo Industrial Nortec',
            'Marzo 2016 - Diciembre 2020. Manufactura de componentes automotrices.',
            'Cartera de 35 cuentas corporativas, crecimiento de 28% anual.',
            '',
            'Ejecutiva de Ventas Senior — Banco Centinela',
            'Junio 2012 - Febrero 2016. Banca empresarial y servicios financieros.',
            '',
        ]
    lines += [
        'FORMACIÓN ACADÉMICA',
        'Licenciatura en Administración de Empresas — Universidad Nacional Autónoma de México (2012)',
        'Diplomado en Dirección Comercial — ITAM (2018)',
        '',
        'HABILIDADES',
        'Venta consultiva, gestión de cuentas clave, pronóstico de ingresos, CRM Salesforce,',
        'negociación de contratos, liderazgo de equipos comerciales.',
        '',
        'IDIOMAS',
        'Español nativo, inglés avanzado (C1).',
    ]
    for line in lines:
        pdf.setFont('Helvetica-Bold' if line.isupper() and line else 'Helvetica', 12 if line == name else 10)
        pdf.drawString(60, y, line)
        y -= 16
    pdf.showPage()
    pdf.save()
    paths.append(path)

print('\n'.join(paths))
