#import yaml
import yaml
from pathlib import Path

_path = Path(__file__).parent

CFG = 'config.yaml'

config_path = _path / CFG
config = {}

with open(config_path) as yaml_config_file:
    try:
        config = yaml.load(yaml_config_file)
    except Exception as e:
        print(e)
