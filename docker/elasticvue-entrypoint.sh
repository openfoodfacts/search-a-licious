#!/usr/bin/env sh

# we want to add basic auth to nginx configuration
# we would have done that with template mechanism,
# but elasticvue use an lod nginx
NGINX_CONF=/etc/nginx/conf.d/elasticvue.conf
if [ -n "$NGINX_BASIC_AUTH_USER_PASSWD" ] && ! ( grep auth_basic  $NGINX_CONF )
then
    echo "setting up basic auth in nginx"
    # create htpasswd file
    echo "$NGINX_BASIC_AUTH_USER_PASSWD" > /etc/nginx/elasticvue_htpasswd
    # change nginx config
    cat >/tmp/nginx_snipet <<END
    auth_basic "Off Search Elasticvue";
    auth_basic_user_file /etc/nginx/elasticvue_htpasswd;
END
    sed -i "/try_files.*/r /tmp/nginx_snipet" $NGINX_CONF

fi

exec "$@"