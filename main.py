#!env python3

from dataclasses import dataclass
from os import path
import os
from typing import List, Optional

MEDUSA_CWD_KEY = '__medusa_cwd_key__'

DELIMITER = '='
FILE_NAME = '.medusa'
CACHE_DIR = '/tmp/medusa'

@dataclass
class Executable:
    key: str
    value: str


class InvariantException(Exception):
    pass


class InvalidCacheException(Exception):
    pass


def invariant(check: bool, msg: str) -> None:
    if not check:
        raise InvariantException(msg)


def get_cache_file() -> str:
    parent_pid = os.getppid()
    return f"{CACHE_DIR}/{parent_pid}"


def get_current_set_aliases() -> Optional[List[str]]:
    if not path.exists(get_cache_file()):
        return None

    set_aliases: List[str] = []
    with open(get_cache_file(), encoding='utf-8') as cache_file:
        cache_line = cache_file.readlines()
        for i, line in enumerate(cache_line):
            # skip first line because it should be the cwd config
            # TODO: validate this
            if i == 0:
                continue

            set_aliases.append(f"unalias {line}")

    return set_aliases


def create_cache(execs: List[Executable]) -> None:
    if not path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    keys_with_new_lines = list(map(lambda exec: f"{exec.key}", execs))
    execs_with_cwd = [f"{MEDUSA_CWD_KEY}{DELIMITER}{os.getcwd()}"] + list(keys_with_new_lines)
    with open(get_cache_file(), 'w', encoding='utf-8') as cache_file:
        cache_file.write('\n'.join(execs_with_cwd))


def get_cwd_for_cache() -> str:
    with open(get_cache_file(), 'r', encoding='utf-8') as cache_file:
        first_line = cache_file.readline()
        if MEDUSA_CWD_KEY not in first_line:
            raise InvalidCacheException("expected first line to be the current working drive")

        if len(first_line.split(DELIMITER)) != 2:
            raise InvalidCacheException("expected medusa cwd to be in the format key=cwd")

        _, cwd = first_line.split('=')
        return cwd


def get_does_medusa_file_exist():
    return os.path.exists(FILE_NAME)


def get_should_clear_aliases() -> bool:
    if not os.path.exists(get_cache_file()):
        return False

    return not os.getcwd().startswith(get_cwd_for_cache())


def get_should_skip_medusa_setup() -> bool:
    return not os.path.exists(get_cache_file()) and not get_does_medusa_file_exist()


def get_executables_from_file(lines: List[str]) -> List[Executable]:
    executables: List[Executable] = []
    for line in lines:
        key_value_pair = line.split(DELIMITER)
        invariant(len(key_value_pair) == 2, f"Invalid executable pair {line}")
        key, value = key_value_pair
        executables.append(Executable(key, value))

    return executables


def cleanup_current_aliases() -> None:
    current_aliases = get_current_set_aliases()
    if current_aliases is None:
        return

    os.remove(get_cache_file())
    cleanup_cmd = ';'.join(current_aliases)
    print(cleanup_cmd)



def load_config_file() -> List[Executable]:
    invariant(path.exists(FILE_NAME), "medusa config file does not exist")

    with open(FILE_NAME, 'r', encoding='utf-8') as config_file:
        bin_lines = config_file.readlines()
        return get_executables_from_file(bin_lines)


def get_full_path(relative_path: str) -> str:
    return path.abspath(relative_path)


def configs_to_string(configs: List[Executable]) -> str:
    config_strings: List[str] = []
    for config in configs:
        config_strings.append(f'alias {config.key}="{config.value}"')

    return ';'.join(config_strings)


def main():
    if get_should_clear_aliases():
        cleanup_current_aliases()
        return

    # TODO: cleanup this logic
    if get_should_skip_medusa_setup():
        return

    if not get_does_medusa_file_exist():
        return

    configs = load_config_file()
    create_cache(configs)
    print(configs_to_string(configs))


if __name__ == '__main__':
    main()
