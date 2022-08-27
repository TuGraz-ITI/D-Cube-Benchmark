FROM nginx
RUN apt-get update && apt-get install -qy pkg-config libfreetype6-dev libjpeg-dev libpng-dev libffi-dev build-essential procps python3 python3-pip uwsgi uwsgi-plugin-python3 curl inetutils-ping curl inetutils-ping zip libcairo2 libpango1.0-0 &&  rm -rf /var/lib/apt/lists/* && rm /etc/nginx/conf.d/default.conf && rm /etc/nginx/nginx.conf && mkdir /storage && chown -R www-data:www-data /storage
ADD --chown=www-data:www-data ./src/ /testbed
VOLUME /storage
ADD ./configs/testbed.ini /etc/uwsgi/apps-enabled
ADD ./init.d/dcube-scheduler /etc/init.d/dcube-scheduler
ADD ./init.d/dcube-evaluation /etc/init.d/dcube-evaluation
ADD ./configs/testbed.conf /etc/nginx/conf.d
ADD ./configs/nginx.conf /etc/nginx/
WORKDIR /testbed
RUN pip3 install -r app/requirements.txt
EXPOSE 80
CMD chown www-data:www-data /storage; service uwsgi start; service nginx start; service dcube-scheduler start; service dcube-evaluation start; tail -F /var/log/nginx/error.log
RUN ln -s /storage/fileupload/ /testbed/app/dcube/static/upload 
