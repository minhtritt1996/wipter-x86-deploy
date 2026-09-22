FROM node:20-alpine

ENV NODE_ENV=production
ENV HOME=/root
ENV WIPTER_USER_DATA=/root/.config/wipter-app

RUN apk add --no-cache bash curl procps ca-certificates && \
    echo -e 'NAME="Debian GNU/Linux"\nVERSION_ID="13"\nVERSION="13 (trixie)"\nPRETTY_NAME="Debian GNU/Linux 13 (trixie)"' > /etc/os-release

WORKDIR /opt/wipter

COPY resources /opt/wipter/resources
COPY app /opt/wipter/app
COPY config /opt/wipter/config-template
COPY config /root/.config/wipter-app
COPY entrypoint.sh /opt/wipter/entrypoint.sh

RUN chmod +x /opt/wipter/entrypoint.sh \
    /opt/wipter/resources/wipter-tunnel/wipter-tunnel_0.1.0_linux/wipter-tunnel \
    /opt/wipter/resources/bin/* \
    /opt/wipter/app/run-headless.js

WORKDIR /opt/wipter/app

EXPOSE 9222 2000

ENTRYPOINT ["/opt/wipter/entrypoint.sh"]
CMD ["node", "--max-old-space-size=128", "run-headless.js"]
