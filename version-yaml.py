import yaml

def main():
    data = {"version-data": {"start-args": {1: {"type": "optionmenu", "args": {"host": {1: {"arg": "link-arg", "standard": 8080, "name": "Start with Port", "type": "entry"}}, "join": {1:{"arg": "link-arg", "standard": "", "name": "Join URL", "type": "entry"}}}}}, "standart-mode": "host"}}
    with open("version.yml", "w") as f:
        yaml.dump(data, f, allow_unicode=True)

if __name__ == "__main__":
    main()