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
                return default

    def append(self, key, value):
        with self.mutex:
            return self.__dic.setdefault(key, []).append(value)

    def remove(self, key):
        with self.mutex:
            if key in self.__dic:
                del self.__dic[key]
            return self.__dic

    def keys(self):
        return self.__dic.keys()

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
registered_tasks = DictWithLock()
registered_task_instance = DictWithLock()

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


def is_registered(module_name, command):
    registered_command_list = registered_commands.getdata(module_name, [])
    logs.debug(f'{command} in {module_name}, {registered_command_list}')
    return command in registered_command_list


def is_registered_task(module_name, task):
    registered_task_list = registered_tasks.getdata(module_name, [])
    logs.debug(f'{task} in {module_name}, {registered_task_list}')
    return task in registered_task_list


def register_command(module_name, command):
    if command not in registered_commands.getdata(module_name, []):
        registered_commands.append(module_name, command)
    logs.debug(f'registered_commands: {registered_commands.getdata(module_name)}')


def register_task(module_name, task):
    if task not in registered_tasks.getdata(module_name, []):
        registered_tasks.append(module_name, task)
    logs.debug(f'registered_tasks: {registered_tasks.getdata(module_name)}')


def save_task_instance(module_name, name, task):
    if name not in registered_tasks.getdata(module_name, []):
        registered_task_instance.setdata(f'{module_name}.{name}', task)


def disable_plugin(plugin_name):
    module_name = f"plugins.{plugin_name}"
    try:
        plugin = import_module(module_name)
        if plugin_name in plugin_list:
            plugin_list.remove(plugin_name)
            if os.path.exists(plugin.__file__):
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


def cancel_registered_task(module_name):
    for name in registered_tasks.getdata(module_name, []):
        instance = registered_task_instance.getdata(f'{module_name}.{name}')
        if instance:
            instance.cancel()
    registered_tasks.remove(module_name)


def clear_registered_handlers_for_module(module_name):
    logs.debug(f'clear registered handlers for {module_name}')
    if module_name:
        for key in registered_handlers:
            if key.startswith(module_name) and not key.endswith(".event"):
                logs.debug(f'remove event handler: {key}')
                event_key = f'{key}.event'
                bot.remove_event_handler(registered_handlers.getdata(key), registered_handlers.getdata(event_key))
                registered_handlers.remove(key)
                registered_handlers.remove(event_key)
        for command in registered_commands.getdata(module_name, []):
            if command in help_messages:
                del help_messages[command]
        if module_name.startswith("pagermaid."):
            module_name = f'plugins.{module_name.split(".")[2]}'
        registered_commands.remove(module_name)
        cancel_registered_task(module_name)


def reload_plugin(plugin_name, times=0):
    times += 1
    if plugin_name.startswith("pagermaid."):
        module_name = plugin_name
    else:
        module_name = f"plugins.{plugin_name}"
    logs.debug(f'plugin: {plugin_name}, module: {module_name}')
    try:
        sys.modules.pop(module_name)
    except KeyError:
        pass
    try:
        import_module(module_name)
        if times >= 1 and plugin_name not in plugin_list:
            plugin_list.append(plugin_name)
            plugin_list.sort()
    except BaseException as exception:
        logs.debug(f"{lang('module')} {plugin_name} {lang('error')}: {exception}, "
                   f"times: {times}")
        if module_name in sys.modules:
            sys.modules.pop(module_name)
        clear_registered_handlers_for_module(module_name)
        if times >= 3:
            if plugin_name in plugin_list:
                plugin_list.remove(plugin_name)
            raise ImportError(f"{plugin_name} {lang('error')}: {exception}")
        reload_plugin(plugin_name, times)


def find_plugin_name_by_command(source_command):
    plugin_name = ""
    for key in registered_handlers.keys():
        if key.endswith(".event"):
            continue
        info = key.split(".")
        if info[-3] == source_command:
            plugin_name = f'pagermaid.modules.{info[2]}' if info[1] == "modules" else info[1]
            break
    return plugin_name


def reload_plugin_for_alias(source_command):
    plugin_name = find_plugin_name_by_command(source_command)
    if plugin_name:
        if plugin_name.startswith("pagermaid."):
            clear_registered_handlers_for_module(plugin_name)
            reload_plugin(plugin_name)
        else:
            clear_registered_handlers_for_module(f'plugins.{plugin_name}')
            reload_plugin(plugin_name)
