# hq-proxies

一个简单的动态代理池，通过较高频率的自检保证池内代理的高可靠性。

# 代码结构
代码分三个部分：
*  一个scrapy爬虫去爬代理网站，获取免费代理，验证后入库   (proxy_fetch)
*  一个scrapy爬虫把代理池内的代理全部验证一遍，若验证失败就从代理池内删除   (proxy_check)
*  一个调度程序用于管理上面两个爬虫   (start.py)

![hq-proxies.png](http://upload-images.jianshu.io/upload_images/4610828-edbea71e6ff36157.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)

# 部署
需要先改一下配置文件hq-proxies.yml，把Redis的地址密码之类的填上，改完后放到/etc/hq-proxies.yml下。
在配置文件中也可以调整相应的阈值和免费代理源和测试页面。
测试页面需要频繁访问，为了节省流量我在某云存储上丢了个helloworld的文本当测试页面了，云存储有流量限制建议大家换掉。。验证方式很粗暴，比较一下网页开头字符串。。

另外写了个Dockerfile可以直接部署到Docker上（python3用的是Daocloud的镜像），跑容器的时候记得把hq-proxies.yml映射到容器/etc/hq-proxies.yml下。
手工部署的话跑`pip install -r requirements.txt`安装依赖包

# 使用
在爬虫中通过redis.srandmember从redis SET中随机拿一个代理用。redis SET和其他用到的key可以在hq-proxies.yml中配置。   
如果代理超时就retry，代理池有自检retry时候再次拿到失效代理的概率很低，但如果代理被BAN的话还是得在redis里srem手工移除。

相关博客：TODO

日志截图：
![Paste_Image.png](http://upload-images.jianshu.io/upload_images/4610828-29e8d33a438a606f.png?imageMogr2/auto-orient/strip%7CimageView2/2/w/1240)
