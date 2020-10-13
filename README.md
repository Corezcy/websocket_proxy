# README
简易代理服务器 (Python 3).

## 配置要求

Python 3 (tested on Python 3.7)  
The 'websockets' module (`pip install websockets`)  
The 'yaml' module (`pip install pyyaml`)  

## 结构说明

```
.
├── README.md
├── config.yaml             #配置文件
├── error_log.log           #输出error级别的日志
├── output_log_all.log      #总日志文件
├── proxy.py                #运行主体(main)
├── launch.py               #启动入口，负责加载配置文件、运行
├── test                    #单元测试文件
│   ├── proxy_tests.py      
│   └── testConfig.yaml
└── websocket_proxpy        
    └── util                
        ├── base.py         #定义fatal_fail处理方法
        ├── jsonutils.py    #json处理方法
        └── loggers.py      #日志记录
```

## 代码说明
### launch.py

`config = yaml.load(open("CONFIG_PATH")) `
>加载配置文件

`WebSocketProxpy(loggers.ConsoleDebugLogger()).run(config)`
>loggers.ConsoleDebugLogger()是日志处理类对象；WebSocketProxpy.run()是代理服务器程序入口

### proxy.py
全局变量：

`is_port_used = {}`

>字典数据类型，记录端口是否被占用，格式：{"port":bool}

-------

`WebSocketProxpy`类内变量简介：
```
logger = None                       #日志处理类对象
host = ""                           #宿主机
port = 0                            #端口号
serverType = "OPEN_URL"             #连接类型
proxied_url = ""                    #eg.ws://10.78.4.163:    
password = ""                       #连接密码
send_suffix = ""                    #json后缀
send_prefix = ""                    #json前缀
proxied_port_list = []              #可用端口列表
requests_per_connection = 10000     #每个连接的最大请求数量
```

-------

`WebSocketProxpy`类内函数简介：

def is_close(json_content):
> 判断手否收到关闭请求，# expects {"url": "ws://0.0.0.0:8081"}

def load_config_from_yaml(self, config_yaml):
> 读取配置文件并赋值

**def run(self,config_yaml):**
> 建立`client--proxy`之间的连接 
> 运行调度函数proxy_dispatcher

**@asyncio.coroutine
def proxy_dispatcher(self, proxy_web_socket, path):**
> 代理服务器调度函数，判断有无端口可用，有端口，则分空闲端口；无端口，则返回忙碌
> 处理`client--proxy--server`之间的请求(调用process_arbitrary_requests)

**def process_arbitrary_requests(self, proxy_web_socket, proxied_web_socket, connection):**
>负责四部分任务：  
>part 1:从client接收请求;  
>part 2:proxy发送请求到server;  
>part 3:proxy接受server返回的数据;  
>part 4:proxy返回数据到client


def connect_to_proxy_server(self, proxied_url_value, proxy_web_socket):
> 建立`proxy--server`之间的链接

def send_to_web_socket_connection_aware(self, proxy_web_socket, proxied_web_socket, request_for_proxy):
> 发送请求服务到`server`



## 使用说明
1、在`config.yaml`中按照注释说明修改`host`、`port`、`proxiedPortList`

2、当使用结束后，发送`{"action": "close"}`到代理服务器，代理服务器执行关闭`client--proxy`和`proxy--server`的指令。

