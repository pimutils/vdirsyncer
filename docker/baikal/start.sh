#!/bin/sh
# Shameless copied from https://raw.githubusercontent.com/ckulka/baikal-docker/master/files/start.sh

# Inject ServerName and ServerAlias if specified
APACHE_CONFIG="/etc/apache2/sites-available/000-default.conf"
if [ ! -z ${BAIKAL_SERVERNAME+x} ]
then
	sed -i "s/# InjectedServerName .*/ServerName $BAIKAL_SERVERNAME/g" $APACHE_CONFIG
fi

if [ ! -z ${BAIKAL_SERVERALIAS+x} ]
then
	sed -i "s/# InjectedServerAlias .*/ServerAlias $BAIKAL_SERVERALIAS/g" $APACHE_CONFIG
fi

apache2-foreground
