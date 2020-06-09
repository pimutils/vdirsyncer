# Based on https://github.com/ckulka/baikal-docker
# Sadly, we can't override the VOLUME it has set, and we want some static
# config.
FROM php:7.4-apache
ENV VERSION 0.7.0

ADD https://github.com/sabre-io/Baikal/releases/download/$VERSION/baikal-$VERSION.zip .
RUN apt-get update && apt-get install -y sqlite3 unzip
RUN unzip -q baikal-$VERSION.zip -d /var/www/

RUN chown -R www-data:www-data /var/www/baikal && \
  docker-php-ext-install pdo pdo_mysql

COPY apache.conf /etc/apache2/sites-enabled/000-default.conf
COPY start.sh /opt/
RUN a2enmod rewrite

COPY baikal.yaml /var/www/baikal/config/baikal.yaml
COPY configure.sql /configure.sql

RUN touch /var/www/baikal/Specific/INSTALL_DISABLED
RUN cat /configure.sql | sqlite3 /var/www/baikal/Specific/db/db.sqlite

RUN chmod -R 777 /var/www/baikal/Specific/ /var/www/baikal/config/

CMD [ "sh", "/opt/start.sh" ]
