# Configuración AWS

La única configuración principal está descrita en [README.md](../README.md).

El proyecto está orientado a una tarea ECS con Nginx, API y MySQL en red awsvpc. Nginx usa 127.0.0.1:8000 y la API usa 127.0.0.1:3306 para MySQL. No hace falta elegir entre configuraciones locales y de EC2 ni ejecutar generadores de tareas.

Las direcciones localhost funcionan únicamente entre contenedores de la misma tarea. La API continúa escuchando en 0.0.0.0:8000; esa es su dirección de escucha, no la dirección de destino que usa Nginx.

Para preservar usuarios, historial y fotos al reemplazar tareas, configura almacenamiento persistente en ECS o servicios externos adecuados. No se presupone que el almacenamiento temporal de Fargate sea persistente. No se crearon recursos en AWS ni se publicó el repositorio.

Referencia oficial: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/fargate-task-networking.html
Almacenamiento: https://docs.aws.amazon.com/AmazonECS/latest/developerguide/bind-mounts.html
