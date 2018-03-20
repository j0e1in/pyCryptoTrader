FROM python:3.6-slim

RUN useradd -ms /bin/bash admin

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  g++ \
  make \
  wget \
  && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
  tar xvf ta-lib-0.4.0-src.tar.gz && \
  cd ta-lib && \
  ./configure --prefix=/usr && \
  make && \
  make install  && \
  cd ..  && \
  rm -rf ta-lib && \
  rm ta-lib-0.4.0-src.tar.gz

COPY requirements-docker.txt /app/

RUN pip install -U pip && \
  pip install -r requirements-docker.txt && \
  pip install ta-lib  # this module needs to be installed after numpy

COPY . /app

USER admin

ENTRYPOINT ["python", "app.py"]

CMD ["--none"]