FROM daocloud.io/python:3.4-onbuild

# Setting timezone
RUN rm -f /etc/localtime
RUN ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime 

CMD [ "python", "./start.py"]