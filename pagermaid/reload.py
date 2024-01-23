import os
import re
import typing
from importlib import import_module, reload
from collections import defaultdict

from telethon.events.common import EventBuilder

from pagermaid import bot, logs, lang, help_messages
from pagermaid.modules import plugin_list

registered_handlers = defaultdict()
registered_command = ""

Callback = typing.Callable[[typing.Any], typing.Any]


def preprocessing_register_handler(key):
    try:
        if registered_handlers[key]:
            event_key = f'{key}.event'
            bot.remove_event_handler(registered_handlers[key], registered_handlers[event_key])
            del registered_handlers[key]
            del registered_handlers[event_key]
    except KeyError:
        pass


def postprocessing_register_handler(key, callback: Callback, event: EventBuilder = None):
    registered_handlers[key] = callback
    registered_handlers[f'{key}.event'] = event


def disable_plugin(plugin_name):
    global registered_command
    try:
        plugin = import_module(f"plugins.{plugin_name}")
        if plugin_name in plugin_list and os.path.exists(plugin.__file__):
            reload(plugin)
        registered_command = ""
    except BaseException as exception:
        logs.info(f"{lang('module')} {plugin_name} {lang('error')}: {exception}")
        finds = find_command(exception)
        if finds:
            registered_command = finds[0]
            key = f'{registered_command}.editedMsg'
            preprocessing_register_handler(key)
            key = f'{registered_command}.newMsg'
            preprocessing_register_handler(key)
            del help_messages[registered_command]
            if plugin_name in plugin_list:
                plugin_list.remove(plugin_name)


def find_command(exception):
    finds = re.compile(r'\"(.*?)\"').findall(f'{exception}')
    return finds


def reload_plugin(plugin_name, is_second_time=False):
    global registered_command
    try:
        plugin = import_module(f"plugins.{plugin_name}")
        if plugin_name in plugin_list and os.path.exists(plugin.__file__):
            reload(plugin)
        registered_command = ""
        if plugin_name not in plugin_list:
            plugin_list.append(plugin_name)
            plugin_list.sort()
    except BaseException as exception:
        logs.info(f"{lang('module')} {plugin_name} {lang('error')}: {exception}")
        if is_second_time:
            raise ImportError(f"{plugin_name} {lang('error')}: {exception}")
        finds = re.compile(r'\"(.*?)\"').findall(f'{exception}')
        if finds:
            registered_command = finds[0]
            key = f'{registered_command}.editedMsg'
            preprocessing_register_handler(key)
            key = f'{registered_command}.newMsg'
            preprocessing_register_handler(key)
            del help_messages[registered_command]
            reload_plugin(plugin_name, True)
        else:
            if plugin_name in plugin_list:
                plugin_list.remove(plugin_name)
            raise ImportError(f"{plugin_name} {lang('error')}: {exception}")
