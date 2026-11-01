FROM python:3.13-slim
ENV DEBIAN_FRONTEND=noninteractive PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends bash ca-certificates curl git openssh-client jq util-linux && rm -rf /var/lib/apt/lists/*
COPY runner-entrypoint.sh /usr/local/bin/neuro-runner-entrypoint
RUN chmod 0755 /usr/local/bin/neuro-runner-entrypoint && useradd --uid 10001 --create-home --shell /bin/bash runner && install -d -o runner -g runner /work /home/runner/.local/state
USER runner
WORKDIR /work
ENV HOME=/home/runner
CMD ["/usr/local/bin/neuro-runner-entrypoint"]
