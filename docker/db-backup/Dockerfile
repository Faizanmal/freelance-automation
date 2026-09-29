FROM postgres:16-alpine

RUN apk add --no-cache aws-cli

COPY scripts/backup.sh /backup.sh
COPY scripts/pg_dump.sh /pg_dump.sh
RUN chmod +x /backup.sh /pg_dump.sh

# Run backup daily at 3 AM
RUN echo "0 3 * * * /pg_dump.sh" >> /etc/crontabs/root

CMD ["/backup.sh"]
