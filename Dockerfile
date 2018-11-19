FROM cytomineuliege/software-groovy-base:v1.4.1

#install python
RUN apt-get update -y && apt-get install -y python3 python3-pip python3-setuptools zlib1g-dev libjpeg-dev
RUN pip3 install requests \
    requests-toolbelt \
    cachecontrol \
    six \
    future \
    shapely \
    numpy \
    opencv-python-headless
    
RUN git clone https://github.com/cytomine-uliege/Cytomine-python-client.git && \
    cd Cytomine-python-client && \
    python3 setup.py build && \
    python3 setup.py install


#copy files
RUN mkdir -p /app
ADD run.py /app/run.py
ADD union4.groovy /app/union4.groovy

RUN mkdir -p /lib && \
    cd /lib && \
    mkdir -p jars && \
    cd jars && \
    wget http://release.cytomine.be/java/cytomine-java-client.jar -O cytomine-java-client.jar

ADD jts-1.13.jar /lib/jars/jts-1.13.jar
    

ENTRYPOINT ["python3", "/app/run.py"]