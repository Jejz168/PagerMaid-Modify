import os
import re
import sys
import threading
import typing
from importlib import import_module, reload

from telethon.events.common import EventBuilder

from pagermaid import bot, logs, lang, help_messages
from pagermaid.modules import plugin_list


class DictWithLock(dict):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.mutex = threading.RLock()
        self.__dic = {}

    def setdata(self, name, value):
        with self.mutex:
            self.__dic[name] = value
            return self.getdata(name)

    def getdata(self, name, default=None):
        with self.mutex:
            if name in self.__dic and self.__dic[name] is not None:
                return self.__dic[name]
            else:
                return default if default is not None else None

    def append(self, key, value):
        with self.mutex:
            return self.__dic.setdefault(key, []).append(value)

    def remove(self, key):
        with self.mutex:
            del self.__dic[key]
            return self.__dic

    def __getitem__(self, name):
        return self.getdata(name)

    def __setitem__(self, name, value):
        return self.setdata(name, value)

    def __iter__(self):
        for key in self.__dic.copy():
            yield key

    def __str__(self):
        return str(self.__dic)


registered_handlers = DictWithLock()
registered_commands = DictWithLock()

Callback = typing.Callable[[typing.Any], typing.Any]


def preprocessing_register_handler(key):
    try:
        if registered_handlers.getdata(key):
            event_key = f'{key}.event'
            bot.remove_event_handler(registered_handlers.getdata(key), registered_handlers.getdata(event_key))
            registered_handlers.remove(key)
            registered_handlers.remove(event_key)
    except KeyError:
        pass


def postprocessing_register_handler(key, callback: Callback, event: EventBuilder = None):
    registered_handlers.setdata(key, callback)
    registered_handlers.setdata(f'{key}.event', event)


def save_command(key, command):
    if command not in registered_commands.getdata(key, []):
        registered_commands.append(key, command)
    logs.debug(f'registered_commands: {registered_commands.getdata(key)}')


def disable_plugin(plugin_name):
    module_name = f"plugins.{plugin_name}"
    try:
        plugin = import_module(module_name)
        if plugin_name in plugin_list and os.path.exists(plugin.__file__):
            reload(plugin)
    except BaseException as exception:
        logs.debug(f"{lang('module')} {plugin_name} {lang('error')}: {exception}")
        finds = find_command(exception)
        logs.debug(f'found command: {finds}')
        if finds:
            clear_registered_handlers_for_module(module_name)


def find_command(exception):
    finds = re.compile(r'\"(.*?)\"').findall(f'{exception}')
    return finds


def clear_registered_handlers_for_module(module_name):
    logs.debug(f'clear registered handlers for {module_name}')
    if module_name:
        for key in registered_handlers:
            logs.debug(f'check key: {key}')
            if key.startswith(module_name) and not key.endswith(".event"):
                logs.debug(f'remove event handler: {key}')
                event_key = f'{key}.event'
                bot.remove_event_handler(registered_handlers.getdata(key), registered_handlers.getdata(event_key))
                registered_handlers.remove(key)
                registered_handlers.remove(event_key)
        for command in registered_commands.getdata(module_name, []):
            if command in help_messages:
                del help_messages[command]


def reload_plugin(plugin_name, is_second_time=False):
    if is_second_time:
        module_name = plugin_name
        plugin_name = module_name[8:]
    else:
        module_name = f"plugins.{plugin_name}"
    try:
        plugin = import_module(module_name)
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        if plugin_name in plugin_list and os.path.exists(plugin.__file__):
            reload(plugin)
        if plugin_name not in plugin_list:
            plugin_list.append(plugin_name)
            plugin_list.sort()
    except BaseException as exception:
        logs.debug(f"{lang('module')} {plugin_name} {lang('error')}: {exception}, "
                   f"is_second_time: {is_second_time}")
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        clear_registered_handlers_for_module(module_name)
        if is_second_time:
            raise ImportError(f"{plugin_name} {lang('error')}: {exception}")
        reload_plugin(plugin_name, True)
