""" PagerMaid async task on background. """
import inspect
from os import path

from pagermaid import bot, logs, lang
from pagermaid.reload import is_registered_task, register_task, save_task_instance


def noop(*args, **kw):
    pass


def AsyncTask(**args):
    name = args.get("name", None)
    if name is None:
        return noop
    back = inspect.getframeinfo(inspect.currentframe().f_back)
    module_name = f'plugins.{path.basename(back.filename)[:-3]}'
    registered = is_registered_task(module_name, name)
    logs.debug(f'check task is registered: {name}, {registered}')
    if registered:
        raise ValueError(f"{lang('error_prefix')} {lang('task')} \"{name}\" {lang('has_reg')}")
    logs.debug(f'module: {module_name}, path: {back.filename}')
    register_task(module_name, name)

    def decorator(task):
        async def handler(context):
            t = bot.loop.create_task(task(context.client))
            save_task_instance(module_name, name, t)
            logs.debug(f'created task: {name}')
        return handler
    return decorator
