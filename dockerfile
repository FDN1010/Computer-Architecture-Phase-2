FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

RUN pip3 install pyyaml

WORKDIR /autograder

COPY . /autograder

RUN chmod +x /autograder/run_autograder

CMD ["/autograder/run_autograder"]