FROM cytomineuliege/software-python2-base:latest

#install java+groovy

RUN apt-get install wget
RUN pip install Pillow

RUN mkdir -p /app
ADD run.py /app/run.py
ADD union4.groovy /app/union4.groovy

RUN mkdir -p /lib && \
    cd lib && \
    mkdir -p jars && \
    cd jars && \
    wget http://release.cytomine.be/java/cytomine-java-client.jar -O cytomine-java-client.jar

ADD jts-1.13.jar /lib/jars/jts-1.13.jar
    

ENTRYPOINT ["python", "/app/run.py"]