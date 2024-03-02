FROM python:3-alpine

ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt

ADD gocd_prometheus.py /usr/local/bin/gocd_prometheus
RUN chmod 755 /usr/local/bin/gocd_prometheus

EXPOSE 8000
CMD ["python", "/usr/local/bin/gocd_prometheus"]
