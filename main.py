#!env python3

from dataclasses import dataclass
from os import path
import os
from typing import List, Optional
from datetime import datetime

MEDUSA_CWD_KEY = '__medusa_cwd_key__'
MEDUSA_DEBUG_KEY = 'MEDUSA_DEBUG'

DELIMITER = '='
FILE_NAME = '.medusa'
CACHE_DIR = '/tmp/medusa'
LOG_FILE =  "debug.log"

ENCODING = 'utf-8'

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


def format_log_msg(ppid: int, msg: str) -> str:
    now = datetime.now()
    dt_string = now.strftime("%d/%m/%Y %H:%M:%S")
    return f"{dt_string} pid: {ppid} msg: {msg}\n"


def log_to_file(msg: str) -> None:
    if os.environ.get(MEDUSA_DEBUG_KEY) in ("", None):
        return
    
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    with open(f"{CACHE_DIR}/{LOG_FILE}", 'a', encoding=ENCODING) as log_file:
        log_file.write(format_log_msg(os.getppid(), msg))


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
            # TODO: validate this and throw exception if it's not valid
            if i == 0:
                continue

            line_without_newline = line.strip("\n")
            set_aliases.append(f"unalias {line_without_newline}")

    return set_aliases


def create_cache(execs: List[Executable]) -> None:
    if not path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    keys_with_new_lines = list(map(lambda exec: f"{exec.key}", execs))
    execs_with_cwd = [f"{MEDUSA_CWD_KEY}{DELIMITER}{os.getcwd()}"] + list(keys_with_new_lines)
    with open(get_cache_file(), 'w', encoding=ENCODING) as cache_file:
        cache_file.write('\n'.join(execs_with_cwd))


def get_cwd_for_cache() -> str:
    with open(get_cache_file(), 'r', encoding=ENCODING) as cache_file:
        first_line = cache_file.readline()
        if MEDUSA_CWD_KEY not in first_line:
            raise InvalidCacheException("expected first line to be the current working drive")

        if len(first_line.split(DELIMITER)) != 2:
            raise InvalidCacheException("expected medusa cwd to be in the format key=cwd")

        _, cwd = first_line.split('=')
        return cwd.strip('\n')


def get_does_medusa_file_exist():
    return os.path.exists(FILE_NAME)


def get_should_clear_aliases() -> bool:
    cache_file = get_cache_file()
    if not os.path.exists(cache_file):
        log_to_file(f"get_should_clear_aliases: {cache_file} path did not exist")
        return False

    starts_with = os.getcwd().startswith(get_cwd_for_cache())
    log_to_file(f"get_should_clear_aliases: cwd: {os.getcwd()} \
        cache_cwd: {get_cwd_for_cache()} starts_with: {starts_with}")
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

    with open(FILE_NAME, 'r', encoding=ENCODING) as config_file:
        bin_lines = config_file.readlines()
        return get_executables_from_file(bin_lines)


def format_configs_as_string(configs: List[Executable]) -> str:
    config_strings: List[str] = []
    for config in configs:
        value_without_newline = config.value.strip("\n")
        config_strings.append(f'alias {config.key}="{value_without_newline}"')

    return ';'.join(config_strings)


def main():
    log_to_file("main ran")
    if get_should_clear_aliases():
        log_to_file("cleaning aliases")
        cleanup_current_aliases()
        return

    # TODO: cleanup this logic
    if get_should_skip_medusa_setup():
        log_to_file("skipping medusa setup")
        return

    if not get_does_medusa_file_exist():
        log_to_file("medusa file does not exist")
        return

    configs = load_config_file()
    create_cache(configs)
    print(format_configs_as_string(configs))


if __name__ == '__main__':
    main()
