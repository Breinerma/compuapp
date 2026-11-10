# Certificado público de Amazon RDS

`global-bundle.pem` procede de https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem.
Es un conjunto público de autoridades certificadoras, no una clave privada ni una credencial.
La API lo utiliza cuando `DB_SSL_CA=/app/certs/global-bundle.pem`, con verificación de certificado y nombre del endpoint.

Antes de desplegar y al anunciar AWS una rotación, actualiza este archivo desde la misma URL HTTPS oficial, reconstruye la imagen y prueba la conexión con RDS. No desactives la verificación TLS para solucionar errores.
