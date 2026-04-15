# Sistema de Seguimiento - Coordinación de Gabinete

Aplicación web local hecha con Flask y SQLite para controlar actividades, avances, vencimientos, evidencias y reportes por dirección.

## Qué incluye
- Login multiusuario
- Rol administrador y rol dirección
- Panel general con gráficas
- Alta de direcciones
- Alta de usuarios
- Alta de actividades/encomiendas
- Vencimientos automáticos
- Registro de avances
- Carga de evidencias
- Reporte general
- Diseño responsivo para celular y computadora

## Usuarios de prueba
### Administrador
- Usuario: `admin`
- Contraseña: `admin123`

### Dirección de Servicios Públicos
- Usuario: `servicios`
- Contraseña: `servicios123`

### Dirección de Obras Públicas
- Usuario: `obras`
- Contraseña: `obras123`

## Cómo ejecutarlo
1. Instala Python 3.11 o superior.
2. Abre terminal dentro de esta carpeta.
3. Instala dependencias:

```bash
pip install -r requirements.txt
```

4. Ejecuta el sistema:

```bash
python app.py
```

5. Abre en tu navegador:

```text
http://127.0.0.1:5000
```

Si quieres entrar desde otro celular o computadora conectados a la misma red local, usa la IP local de la computadora donde corre el sistema, por ejemplo:

```text
http://192.168.1.20:5000
```

## Dónde cambiar logos
Sustituye estos archivos por los oficiales del Ayuntamiento:
- `static/logo_bahia.png`
- `static/logo_escudo.png`

## Notas importantes
- La base de datos se guarda en `database.db`
- Los archivos subidos se guardan en `static/uploads`
- Antes de usarlo en producción conviene cambiar la `SECRET_KEY` en `app.py`
- Para un uso institucional real posterior, lo ideal sería migrarlo a PostgreSQL y servidor en línea



## Adecuaciones incluidas en esta versión
- Reportes con filtro por dirección para administrador y ordenados por dirección.
- Mensajería interna institucional con recibidos, enviados, detalle y respuesta.
- Contador de mensajes no leídos en la barra superior.
- Solo el administrador puede eliminar actividades.
- Botón para enviar mensaje desde el detalle de actividad.
- Bloque final de arranque corregido para Railway.
