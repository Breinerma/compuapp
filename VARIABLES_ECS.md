# Variables de los contenedores

Ya están incorporadas en los Dockerfile y en Compose. No se necesita un archivo .env. Si las escribes también en la definición de tarea ECS, utiliza estos mismos valores.

## MySQL · imagen naturalens-db

```text
MYSQL_DATABASE=naturalens
MYSQL_USER=naturalens
MYSQL_PASSWORD=JCMMCMAPbmamyma
MYSQL_ROOT_PASSWORD=jcmmcmmapBMAMYMA
```

## API · imagen naturalens-api

```text
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=naturalens
DB_USER=naturalens
DB_PASSWORD=JCMMCMAPbmamyma
COOKIE_SECURE=false
UPLOAD_DIR=/app/uploads
```

`COOKIE_SECURE=false` corresponde al acceso por IP mediante HTTP. Cámbialo a `true` si configuras HTTPS. La API usa la cuenta `naturalens`, no la cuenta root.

## Nginx · imagen naturalens-web

No necesita variables de entorno de la aplicación. Escucha en el puerto 80 y apunta a `http://127.0.0.1:8000`.

Los tres contenedores deben pertenecer a la misma tarea ECS con red awsvpc. Los valores están escritos en texto claro en el código y en las imágenes, como se solicitó. MySQL aplica estas variables al inicializar una base nueva; no cambian las contraseñas de una base ya existente.
