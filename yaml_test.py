import yaml

if __name__ == '__main__':
    CONFIG_FILE_NAME = "config.yaml"
    config = yaml.load(open(CONFIG_FILE_NAME))
    server_config = config['configuration']['serverConfiguration']
    proxied_url_list = host = server_config['proxiedUrl']
