FROM python:3.10

MAINTAINER Greg King "greg@kooji.com"

WORKDIR /app
COPY requirements.txt ./

RUN pip3 install -r requirements.txt

COPY light.py main.py termdates.py ./

CMD ["/app/main.py"]
ENTRYPOINT [ "python3" ]