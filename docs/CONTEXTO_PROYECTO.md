# AI Report Builder — Contexto del Proyecto

## Instrucción para Claude

Actuá como Arquitecto de Software Senior. Estamos desarrollando una aplicación web (Streamlit) para automatizar la generación de reportes mensuales de productividad del Contact Center del Hospital Alemán (Buenos Aires). El usuario no es desarrollador.

## Estado actual (v1.1)

### Lo que ya funciona:
- **App web con Streamlit** desplegada en Streamlit Cloud (el usuario accede por URL)
- **Data Loader**: lee CSVs de Tecnovoz (separador `;`, decimales `,`, encoding UTF-8)
- **Skill Mapper**: reconoce automáticamente 22 habilidades por nombre de archivo y las agrupa en 6 campañas
- **KPI Engine**: calcula 8 indicadores (Recibidas, Atendidas, Prom. Rec., Prom. At., NA%, Conversación, Demora, Abandono)
- **Chart Engine**: genera 6 tipos de gráficos con matplotlib (colores navy #1B3A5C / celeste #5B9BD5 / verde #4CAF50)
- **PPTX Generator**: genera PowerPoint con portada, KPI cards, gráficos embebidos, tabla de habilidades (python-pptx, sin Node.js)
- **Plugin Architecture**: el Contact Center es un plugin; se pueden agregar otros reportes sin modificar el código base

### Campañas y habilidades:
- **Turnos** (12): Turnos Estudios, Turnos PM Estudios, Turno Consulta, Turnos PM Consulta, Gipfel Cober, Gipfel PM, Donacion, 0800 onco, Osde 210, TelePerfomance, TelePerf Cons, TelePerf PM Cons
- **Conmutador** (5): Conmutador, Busqueda Personas, Camilleros, Sede Caballito, RechazoComm
- **Plan Médico** (2): PM Consultas, 0800 coca cola
- **Portal** (2): Portal Digital, Portal Paciente
- **Agendas** (1): Agendas medicas
- **Camp HA** (1): Camp HA

### Formato de archivos CSV:
- Patrón de nombre: `{Nombre Habilidad}_{mesAño}.csv` (ej: `Turnos PM Estudios_jun26.csv`)
- Columnas: NUMDAY, TRANSFER, NOTRANSFER, TOTALCALLS, PCTATT, AVGCONNWAIT, AVGABNWAIT, AVGTALKTIME, SVCLEVEL, SLCALLS, LOGDATE
- Fila "Total" al final (se elimina automáticamente)
- Fuente: sistema Tecnovoz

### Estructura de carpetas:
```
ai-report-builder/
├── streamlit_app.py              ← App web principal
├── requirements.txt
├── .streamlit/config.toml
├── config/settings.yaml
├── app/
│   ├── config.py                 ← Pydantic settings
│   ├── core/
│   │   ├── plugin_registry.py    ← Sistema de plugins (ABC + registry)
│   │   └── pipeline.py           ← Orquestador de etapas
│   ├── data_loader/
│   │   ├── csv_loader.py         ← Lectura de CSVs Tecnovoz
│   │   ├── validator.py          ← Validación de datos
│   │   └── skill_mapper.py       ← Reconocimiento de habilidad/campaña
│   ├── kpi_engine/
│   │   └── calculator.py         ← Cálculo de KPIs + variaciones
│   ├── chart_engine/
│   │   ├── chart_styles.py       ← Estilos fijos (colores, fuentes)
│   │   └── renderer.py           ← 6 tipos de gráficos
│   ├── ai_engine/
│   │   └── client.py             ← Wrapper Claude API (sin conectar aún)
│   ├── report_generator/
│   │   └── pptx_python.py        ← Generador PPTX con python-pptx
│   └── plugins/
│       └── contact_center/
│           └── plugin.py          ← Plugin CC con schema, KPIs, charts, prompts
```

### Reporte PDF de referencia:
El reporte tiene 19 páginas:
1. Portada (logos HA + JCI, título, período, fuente)
2. Datos generales (5 KPI cards + variaciones vs mes anterior)
3. Todas las campañas (tiempos + gráfico diario barras+línea)
4. Sin Gipfel (mismos KPIs filtrados)
5. Distribución por día de semana
6. Análisis de campañas (barras horizontales + donut)
7-11. Campaña individual (Conmutador, Plan Médico, Portal, Turnos, Agendas)
12. Evolución mensual (tabla + gráfico Ene-Dic)
13. Llamadas salientes (KPIs + distribución resultado + diaria)
14-15. Análisis de habilidades (top 10 + tabla 19 habilidades)
16-19. Anexos (productividad diaria por campaña)

### Lo que falta desarrollar:
1. **Logos** en la portada del PPTX (Hospital Alemán + Joint Commission International)
2. **IA** conectada (resumen ejecutivo, conclusiones, recomendaciones con Claude API)
3. **Datos históricos**: cargar CSVs de meses anteriores para evolución mensual y variaciones vs mes anterior
4. **Llamadas salientes**: parser del archivo separado (página 13 del reporte)
5. **Anexos**: tablas de productividad diaria por campaña (páginas 16-19)
6. **PDF como salida alternativa** (ReportLab)
7. **Nuevos tipos de reporte**: Turnos, Laboratorio, Admisiones, Oncología (cada uno como nuevo plugin)

### Tecnologías:
Python 3.11+, Streamlit, pandas, matplotlib, python-pptx, pydantic, PyYAML

### Notas importantes:
- El usuario NO es desarrollador — la app debe ser usable sin conocimientos técnicos
- Los gráficos NUNCA deben cambiar de estilo entre meses (colores, fuentes, tamaños fijos)
- La IA solo redacta texto, nunca inventa datos
- Formato argentino: punto para miles, coma para decimales
