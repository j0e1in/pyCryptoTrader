FROM python:3.6-slim

RUN useradd -ms /bin/bash admin

WORKDIR /app
COPY . /app

RUN apt-get update && apt-get install -y --no-install-recommends \
  g++ \
  git \
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

RUN pip install -r requirements-docker.txt && \
  pip install ta-lib  # this module needs to be installed after numpy

# RUN git clone https://github.com/matplotlib/mpl_finance.git  && \
#     cd mpl_finance  && \
#     python setup.py install  && \
#     cd ..  && \
#     rm -rf mpl_finance

USER admin

CMD ["bash"]