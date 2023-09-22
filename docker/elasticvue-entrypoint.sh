#!/usr/bin/env sh

# we want to add basic auth to nginx configuration
# we would have done that with template mechanism,
# but elasticvue use an lod nginx
NGINX_CONF=/etc/nginx/conf.d/elasticvue.conf
# prepare snippet to eventually add to conf
>/tmp/nginx_snippet
CONF_MODIFIED=false
if [ -n "$NGINX_BASIC_AUTH_USER_PASSWD" ] && ! ( grep auth_basic  $NGINX_CONF )
then
    CONF_MODIFIED=true
    echo "setting up basic auth in nginx"
    # create htpasswd file
    echo "$NGINX_BASIC_AUTH_USER_PASSWD" > /etc/nginx/elasticvue_htpasswd
    # change nginx config
    cat >>/tmp/nginx_snippet <<END
    # add auth basic globally
    auth_basic "Off Search Elasticvue";
    auth_basic_user_file /etc/nginx/elasticvue_htpasswd;
END
fi
if ! (grep "location /es/ {" $NGINX_CONF)
then
    CONF_MODIFIED=true
    echo "setting up ES access in nginx"
    cat >>/tmp/nginx_snippet <<END
    # give access to ES through this url

    location /es/ {
        proxy_pass http://es01:9200/;
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header Host \$http_host;
        proxy_pass_header Access-Control-Allow-Origin;
        proxy_pass_header Access-Control-Allow-Methods;
        proxy_hide_header Access-Control-Allow-Headers;
        add_header Access-Control-Allow-Headers 'X-Requested-With, Content-Type';
        add_header Access-Control-Allow-Credentials true;
    }
END
fi
if [ "$CONF_MODIFIED" == "true" ]
then
    sed -i "/^ *access_log .*/r /tmp/nginx_snippet" $NGINX_CONF
fi

exec "$@"
