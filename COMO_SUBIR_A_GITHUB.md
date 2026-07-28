# Cómo actualizar la app en GitHub — SOLUCIÓN AL PROBLEMA DE app/app

## El problema que tenías

En tu repositorio quedó una estructura ANIDADA MAL:

    app/
      app/            ← ¡ESTO ESTABA MAL!
        data_loader/
        ...

Debería ser así (sin la segunda "app"):

    app/
      data_loader/
      chart_engine/
      report_generator/
      ...

Por eso Streamlit no encontraba los archivos nuevos y seguía usando los viejos.

## La solución definitiva: borrar y recrear el repo

Esto garantiza que no queden archivos viejos ni carpetas anidadas mal.

### Paso 1 — Borrar el repositorio actual
1. Entrá a tu repositorio en GitHub
2. Clic en "Settings" (Configuración) — arriba del todo
3. Bajá hasta el final → sección roja "Danger Zone"
4. Clic en "Delete this repository"
5. Escribí el nombre para confirmar y borralo

### Paso 2 — Crear un repositorio nuevo
1. Clic en el "+" arriba a la derecha → "New repository"
2. Ponele el mismo nombre de antes (ej: ai-report-builder)
3. Dejalo como "Public"
4. Clic en "Create repository"

### Paso 3 — Subir los archivos CORRECTAMENTE
1. Descomprimí `ai-report-builder.zip` en tu computadora.
   IMPORTANTE: al descomprimir NO te va a crear una carpeta "ai-report-builder".
   Te va a dejar directamente: la carpeta "app", "config", el archivo
   "streamlit_app.py", "requirements.txt", etc.

2. En el repositorio nuevo, clic en "uploading an existing file"

3. Seleccioná TODOS esos archivos y carpetas juntos y arrastralos:
   - app  (carpeta)
   - config  (carpeta)
   - docs  (carpeta)
   - tests  (carpeta)
   - .streamlit  (carpeta)
   - streamlit_app.py
   - requirements.txt
   - requirements_web.txt
   - main.py
   - README.md

4. GitHub va a mostrar que sube todo con las subcarpetas.
   Escribí un mensaje y clic en "Commit changes".

### Paso 4 — Verificar que quedó bien
Navegá en GitHub y confirmá que la ruta es:

    app/data_loader/csv_loader.py     ✅ CORRECTO

y NO:

    app/app/data_loader/csv_loader.py  ❌ MAL

### Paso 5 — Reconectar Streamlit
1. Andá a share.streamlit.io
2. Si la app da error, clic en "Reboot app" o borrala y creala de nuevo
   apuntando a "streamlit_app.py"

## Cómo saber que funcionó
Cuando abras la app y generes un reporte:
- La portada debe tener el logo de Hospital Alemán + JCI
- Los anexos con muchos días deben verse en 2 columnas dentro del slide
