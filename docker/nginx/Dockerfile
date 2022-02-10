FROM nginx:stable

# Copy nginx config and static content. Must be run from root
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY src/nextbus/static /static

# Redirect access and error logging to stdout/stderr respectively
RUN \
  ln -sf /dev/stdout /var/log/nginx/access.log && \
  ln -sf /dev/stderr /var/log/nginx/error.log
