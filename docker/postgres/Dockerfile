FROM postgres:13-bullseye

# Set locale to en_GB
RUN localedef -i en_GB -c -f UTF-8 -A /usr/share/locale/locale.alias en_GB.UTF-8

# Set language and database credentials
ENV LANG en_GB.UTF-8
ENV LANGUAGE en_GB.UTF-8
ENV POSTGRES_USER prod
ENV POSTGRES_PASSWORD hello_world
ENV POSTGRES_DB nextbus
