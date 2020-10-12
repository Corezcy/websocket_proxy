import yaml

if __name__ == '__main__':
    CONFIG_FILE_NAME = "config.yaml"
    config = yaml.load(open(CONFIG_FILE_NAME))
    server_config = config['configuration']['serverConfiguration']
    host = server_config['proxiedPortList']
    print(host)
    print("---------------")
    is_used=[]
    for i in range(10):
        is_used.append(False)
        print(is_used[i])
    print(len(is_used))
    print("---------------")
    map={"9192":False}
    map["9193"] = True
    print(map.get(1))


