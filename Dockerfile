FROM python:2-alpine

RUN pip install prometheus_client
RUN pip install yagocd

ADD gocd_prometheus.py /usr/local/bin/gocd_prometheus
RUN chmod 755 /usr/local/bin/gocd_prometheus

CMD ["python", "/usr/local/bin/gocd_prometheus"]
