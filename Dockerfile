FROM python:3.5-jessie as build-env
ENV PYTHONUNBUFFERED 1
RUN mkdir /code
WORKDIR /code
ADD requirements.txt /code/
RUN pip install -r requirements.txt

FROM gcr.io/distroless/python3
COPY --from=build-env /usr/lib/x86_64-linux-gnu /usr/lib/x86_64-linux-gnu
COPY --from=build-env /lib/x86_64-linux-gnu/libcom_err.so.2 /lib/x86_64-linux-gnu/
COPY --from=build-env /lib/x86_64-linux-gnu/libkeyutils.so.1 /lib/x86_64-linux-gnu/

COPY --from=build-env /usr/local/bin /usr/local/bin
COPY --from=build-env /usr/local/lib /usr/local/lib

COPY . /comware
WORKDIR /comware

ENV PYTHONPATH=/usr/local/lib/python3.5/site-packages
ENV LD_LIBRARY_PATH=/usr/local/lib
ENV ALLOWED_HOSTS=127.0.0.1

ENTRYPOINT ["/usr/local/bin/python", "manage.py", "migrate","--noinput"]
ENTRYPOINT [ "/usr/local/bin/gunicorn", "comware.wsgi:application",  "--workers=5",  "--bind=localhost:8888"]



#FROM python:3.5-jessie
#ENV PYTHONUNBUFFERED 1
#ENV ALLOWED_HOSTS=127.0.0.1
#ADD . .
#RUN pip install -r requirements.txt
#CMD python manage.py migrate --noinput
#CMD gunicorn comware.wsgi:application --workers 4 --bind=localhost:8888
