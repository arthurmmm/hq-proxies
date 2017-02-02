FROM daocloud.io/python:3-onbuild

# Setting timezone
rm -f /etc/localtime
ln -sf /usr/share/zoneinfo/Asia/Shanghai /etc/localtime 

CMD [ "python", "./start.py" ]