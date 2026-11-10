FROM nginx:alpine
# Construir desde la raíz: docker build -f nginx/Dockerfile -t naturalens-web .
COPY frontend/ /usr/share/nginx/html/
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
