# 📊 AI Report Builder — Hospital Alemán

Aplicación web para generar automáticamente reportes mensuales de **Productividad del Contact Center** a partir de archivos CSV de Tecnovoz.

---

## ¿Cómo funciona?

1. **Abrís la página web** en tu navegador
2. **Subís los archivos CSV** del mes (uno por habilidad)
3. **Revisás los indicadores** calculados automáticamente
4. **Descargás el reporte** en PowerPoint (.pptx)

No necesitás saber programar. Solo subís los archivos y listo.

---

## Instalación local (una sola vez)

### Prerequisitos
- Python 3.11 o superior → [Descargar Python](https://www.python.org/downloads/)

### Pasos

1. Descargá y descomprimí este proyecto
2. Abrí una terminal (o PowerShell en Windows) en la carpeta del proyecto
3. Ejecutá estos comandos:

```bash
pip install -r requirements_web.txt
```

4. Para abrir la aplicación:

```bash
streamlit run streamlit_app.py
```

5. Se abrirá automáticamente en tu navegador (http://localhost:8501)

---

## Formato de archivos CSV esperado

Los archivos deben ser exportados de **Tecnovoz** con estas características:

- Separador: `;` (punto y coma)
- Decimales: `,` (coma)
- Encoding: UTF-8
- Columnas requeridas: `NUMDAY`, `TRANSFER`, `NOTRANSFER`, `TOTALCALLS`, `PCTATT`, `AVGCONNWAIT`, `AVGABNWAIT`, `AVGTALKTIME`, `LOGDATE`

Ejemplo de nombre: `PM_Consultas_may26.csv`, `Conmutador_may26.csv`

---

## Estructura del proyecto

```
ai-report-builder/
├── streamlit_app.py          ← Aplicación web (lo que ejecutás)
├── app/
│   ├── data_loader/          ← Lectura y validación de CSVs
│   ├── kpi_engine/           ← Cálculo de indicadores
│   ├── chart_engine/         ← Generación de gráficos
│   ├── report_generator/     ← Generación del PPTX
│   ├── ai_engine/            ← Integración con IA (opcional)
│   └── plugins/
│       └── contact_center/   ← Configuración del reporte CC
├── config/
│   └── settings.yaml         ← Configuración global
└── requirements_web.txt      ← Dependencias
```
