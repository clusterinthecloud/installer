FROM hashicorp/terraform:0.12.21

ARG GCLOUD=272.0.0

RUN apk add --update bash openssh curl python3
RUN pip3 install petname

RUN curl https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/google-cloud-sdk-${GCLOUD}-linux-x86_64.tar.gz> cloud-sdk.tgz && \
    tar zxf cloud-sdk.tgz && \
    ./google-cloud-sdk/install.sh --path-update=true && \
    google-cloud-sdk/bin/gcloud config set --installation component_manager/disable_update_check true && \
    google-cloud-sdk/bin/gcloud config set disable_usage_reporting false && \
    rm -rf cloud-sdk.tgz

ENV PATH=/google-cloud-sdk/bin:$PATH

WORKDIR /root

ADD install_citc.py .

ENTRYPOINT ["bash"]
