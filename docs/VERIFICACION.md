# Verificación de la configuración final para ECS

- Nginx apunta directamente a 127.0.0.1:8000; la API usa MySQL en 127.0.0.1:3306 dentro de la misma tarea.
- La API espera el arranque de MySQL en lugar de fallar en el primer intento de conexión.
- Construidas las imágenes finales de web y API.
- Compose validado mediante config --quiet.
- Prueba aislada con tres contenedores Linux y MySQL real, compartiendo red como awsvpc: web y /api/health respondieron correctamente, con 37 clases del modelo. No se publicaron puertos ni se alteraron los datos existentes.
- Los contenedores y datos desechables de la prueba se eliminaron al terminar.
- Retiradas las alternativas de EC2, los generadores de tareas y los scripts de despliegue que no eran necesarios para la petición.
- Las contraseñas solicitadas están incorporadas en texto claro en db/Dockerfile, api/Dockerfile y Compose, sin depender de .env.
- No se publicó en GitHub ni se desplegó en una cuenta AWS. La configuración de contraseñas, red y almacenamiento persistente de ECS se realiza en esa cuenta.

Actualización de credenciales: Compose validado sin requerir variables de .env e imágenes de base de datos y API construidas correctamente. MySQL inicializa una base nueva con estas credenciales; no se cambiaron contraseñas de bases existentes.
