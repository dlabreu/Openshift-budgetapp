FROM registry.fedoraproject.org/fedora:40

LABEL name="budgetapp" \
      version="1.0" \
      description="Budget tracking Flask app"

USER 0

RUN dnf install -y \
        python3.11 \
        python3.11-devel \
    && dnf clean all \
    && rm -rf /var/cache/dnf \
    && python3.11 -m ensurepip --upgrade \
    && python3.11 -m pip install --upgrade pip

WORKDIR /app

COPY Openshift-App/requirements.txt .
RUN python3.11 -m pip install --no-cache-dir -r requirements.txt

COPY Openshift-App/ .

RUN mkdir -p /app/data \
    && chmod -R 777 /app/data

RUN chown -R 0:0 /app \
    && chmod -R g=u /app

USER 1001

EXPOSE 8080

CMD ["python3.11", "main.py"]
