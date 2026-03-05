FROM nginx:alpine

RUN apk add --no-cache certbot openssl

COPY nginx.conf /etc/nginx/nginx.conf.template
COPY . /usr/share/nginx/html

EXPOSE 80 443

CMD ["sh", "-c", "\
    if [ ! -f /etc/letsencrypt/live/botdiscord.ru/fullchain.pem ]; then \
        echo 'Получение первого сертификата...' && \
        certbot certonly --standalone -d botdiscord.ru -d www.botdiscord.ru --non-interactive --agree-tos --email admin@botdiscord.ru --nginx; \
    fi && \
    envsubst '\$HOST' < /etc/nginx/nginx.conf.template > /etc/nginx/nginx.conf && \
    certbot renew --quiet && \
    exec nginx -g 'daemon off;'"]
