#!/bin/sh
# -*- coding: utf-8 -*-

export WORKON_HOME=$HOME/.virtualenvs
source /usr/local/bin/virtualenvwrapper.sh
workon amwatcher-spider
cd /root/git/proxy_spider/
nohup /root/git/proxy_spider/start.py >/dev/null 2>&1 &