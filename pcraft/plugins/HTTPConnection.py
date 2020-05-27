from scapy.all import Ether, IP, TCP
from pcraft.PluginsContext import PluginsContext
from . import _utils as utils
import random
import os
import time

class PCraftPlugin(PluginsContext):
    name = "HTTPConnection"
    required = ["ip-dst", "domain"]
    
    def help(self):
        helpstr="""
Creates an http request and response with a random content of a length of 122.

### Examples

#### 1: A Simple HTTP Connection
```
httpconnect:
  _plugin: HTTPConnection
  method: "GET"
  uri: "/index.php"
  user-agent: "Mozilla/5.0"
  _next: done
```
"""
        return helpstr
    
    def __init__(self, session, plugins_data):
        super().__init__(session, plugins_data)
        self.plugins_data = plugins_data
        self.random_client_ip = utils.getRandomIP("192.168.0.0/16", ipfail="172.16.42.42")
        self.session = session
        
    def run(self, script=None):
        self.check_required(script, self.required)
        
        self.set_value_or_default(script, "ip-src", self.random_client_ip.get())
        self.set_value_or_default(script, "ip-dst", "0.0.0.0") # Default is never applied since it is a requirement
        self.set_value_or_default(script, "port-src", random.randint(4096,65534))
        self.set_value_or_default(script, "domain", "example.com") # Default is never applied since it is a requirement
        self.set_value_or_default(script, "method", "GET") 
        self.set_value_or_default(script, "user", "") 
        self.set_value_or_default(script, "user-agent", "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:42.0) Gecko/20100101 Pcraft/0.0.7") 
        self.set_value_or_default(script, "uri", "/")
        self.set_value_or_default(script, "resp-httpver", "HTTP/1.1")
        self.set_value_or_default(script, "resp-code", "200 OK")
        self.set_value_or_default(script, "resp-server", "nginx")
        self.set_value_or_default(script, "resp-content-type", "text/html")
        self.set_value_or_default(script, "resp-content", "<html><body>Hello, you!</body></html>")
        
        last_ack = utils.append_tcp_three_way_handshake(self.plugins_data, self.getvar("port-src"))

        user = self.getvar("user")
        if user != "":
            user = "\r\nUser: %s" % user
            
        httpreq_string = "{method} {uri} HTTP/1.1\r\nAccept: */*\r\nUser-Agent: {useragent}\r\nHost:{host}{user}\r\nConnection: Keep-Alive\r\n\r\n".format(
            method=self.getvar("method"),
            uri=self.getvar("uri"),
            useragent=self.getvar("user-agent"),
            host=self.getvar("domain"),
            user=user)

        datestr = time.strftime("%a, %d %b %Y %H:%M:%S %Z",time.gmtime())
        httpresp_string = "{httpver} {code}\r\nServer: {server}\r\nDate: {date}\r\nContent-Type: {contenttype}\r\nContent-Length: {contentlen}\r\nConnection: keep-alive\r\nX-Powered-By: PHP/5.3.11-1~dotde b0\r\n\r\n{content}".format(
            httpver=self.getvar("resp-httpver"),
            code=self.getvar("resp-code"),
            server=self.getvar("resp-server"),
            date=datestr,
            contenttype=self.getvar("resp-content-type"),
            contentlen=len(self.getvar("resp-content")),
            content=self.getvar("resp-content")) 
        
        # httpget_string = "POST /g.php HTTP/1.1\r\nAccept: */*\r\nUser-Agent: Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; InfoPath.1)\r\nHost:" + self.plugins_data._get("domain") + "\r\nContent-Length:122\r\nConnection: Keep-Alive\r\nCache-Control: no-cache\r\n\r\n" + str(os.urandom(122))
        httpreq1 = Ether() / IP(src=self.getvar("ip-src"),dst=self.getvar("ip-dst")) / TCP(sport=self.getvar("port-src"),dport=80, seq=last_ack[TCP].ack, ack=last_ack[TCP].seq, flags="P""A") / httpreq_string
        self.plugins_data.pcap.append(httpreq1)

        ack = Ether() / IP(src=self.getvar("ip-src"),dst=self.getvar("ip-dst")) / TCP(sport=80, seq=httpreq1[TCP].ack, ack=httpreq1[TCP].seq+len(httpreq1[TCP])-20, dport=self.getvar("port-src"), flags="A")
        self.plugins_data.pcap.append(ack)
        
        httpreq2 = Ether() / IP(src=self.getvar("ip-dst"),dst=self.getvar("ip-src")) / TCP(sport=80,dport=self.getvar("port-src"), seq=httpreq1[TCP].ack, ack=ack[TCP].ack, flags="P""A") / httpresp_string
        self.plugins_data.pcap.append(httpreq2)
        
        
        return script["_next"], self.plugins_data

