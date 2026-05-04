#!/bin/bash
cat > /etc/nginx/sites-enabled/speedbot << 'ENDCFG'
server {
    server_name chatbotad.io www.chatbotad.io 54.226.67.188 speedbot.aicraftsmen.com;
    client_max_body_size 25M;

    location /static/ {
        alias /home/ubuntu/speedbot/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/speedbot/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    listen 443 ssl;
    ssl_certificate /etc/letsencrypt/live/chatbotad.io/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/chatbotad.io/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;
}

server {
    listen 80;
    server_name chatbotad.io www.chatbotad.io speedbot.aicraftsmen.com;
    return 301 https://$host$request_uri;
}

server {
    listen 80;
    server_name 54.226.67.188;
    client_max_body_size 25M;

    location /static/ {
        alias /home/ubuntu/speedbot/staticfiles/;
    }

    location /media/ {
        alias /home/ubuntu/speedbot/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
ENDCFG

nginx -t && systemctl reload nginx && echo "NGINX OK" || echo "NGINX FAILED"
