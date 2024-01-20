""" Pagermaid backup and recovery plugin. """
import json
import os
import tarfile
from asyncio import sleep
from datetime import datetime
from distutils.util import strtobool
from io import BytesIO
from traceback import format_exc

from telethon.tl.types import MessageMediaDocument

from pagermaid import config, redis_status, redis, scheduler
from pagermaid.listener import listener
from pagermaid.utils import alias_command, upload_attachment, lang

pgm_backup_zip_name = "pagermaid_backup.tar.gz"
pgm_backup_redis_key = "pgmBackup"
pgm_backup_state_redis_key = f'{pgm_backup_redis_key}:state'
pgm_backup_chatid_redis_key = f'{pgm_backup_redis_key}:chatId'
pgm_backup_exclude_filetypes_redis_key = f'{pgm_backup_redis_key}:excludeFiletypes'
is_enable_pgm_backup_job = False
pgm_backup_chatid = int(config['log_chatid'])
pgm_backup_exclude_filetypes = []
if redis_status():
    is_enable_pgm_backup_job = True if redis.get(pgm_backup_state_redis_key) else False
    pgm_backup_chatid_redis = redis.get(pgm_backup_chatid_redis_key)
    if pgm_backup_chatid_redis:
        pgm_backup_chatid = int(pgm_backup_chatid_redis.decode())
    pgm_backup_exclude_filetypes_redis = redis.get(pgm_backup_exclude_filetypes_redis_key)
    if pgm_backup_exclude_filetypes_redis:
        pgm_backup_exclude_filetypes = pgm_backup_exclude_filetypes_redis.decode().split(",")


def make_tar_gz(output_filename, source_dirs: list, exclude_filetypes: list):
    """
    压缩 tar.gz 文件
    :param output_filename: 压缩文件名
    :param source_dirs: 需要压缩的文件列表
    :param exclude_filetypes: 排除的文件类型
    :return: None
    """
    with tarfile.open(output_filename, "w:gz") as tar:
        for i in source_dirs:
            tar.add(i, arcname=os.path.basename(i),
                    filter=lambda tarinfo: None if os.path.splitext(tarinfo.name)[1] in exclude_filetypes else tarinfo)


def un_tar_gz(filename, dirs):
    """
    解压 tar.gz 文件
    :param filename: 压缩文件名
    :param dirs: 解压后的存放路径
    :return: bool
    """
    try:
        t = tarfile.open(filename, "r:gz")
        t.extractall(path=dirs)
        return True
    except Exception as e:
        print(e, format_exc())
        return False


@scheduler.scheduled_job("cron", day="*/7", hour="0", minute="0", second="20", id="backup_job")
async def run_every_7_day():
    if is_enable_pgm_backup_job:
        await do_backup()


@listener(is_plugin=True, outgoing=True, command=alias_command("backup"),
          description=lang('backup_des'), parameters="[enable/disable/chatId/ex <e.g., .ttc>]")
async def backup(context):
    global is_enable_pgm_backup_job, pgm_backup_chatid
    p = context.parameter
    if len(p) > 0:
        if p[0] == "enable":
            is_enable_pgm_backup_job = True
            redis.set(pgm_backup_state_redis_key, "true")
            await context.edit(f'{lang("apt_enable")}{lang("backup_scheduler")}')
        elif p[0] == "disable":
            is_enable_pgm_backup_job = False
            redis.delete(pgm_backup_state_redis_key)
            await context.edit(f'{lang("apt_disable")}{lang("backup_scheduler")}')
        elif p[0] == "ex":
            try:
                filetype = p[1]
                if filetype[0] != ".":
                    await context.edit(lang("backup_filetype_input_error"))
                    return
                pgm_backup_exclude_filetypes.append(filetype)
                redis.set(pgm_backup_exclude_filetypes_redis_key, ",".join(pgm_backup_exclude_filetypes))
                await context.edit(lang("backup_filetype_suc"))
            except IndexError:
                await context.edit(lang("merge_command_error"))
        else:
            try:
                pgm_backup_chatid = int(p[0])
            except ValueError:
                await context.edit(lang("backup_chatid_error"))
                return
            redis.set(pgm_backup_chatid_redis_key, pgm_backup_chatid)
            await context.edit(lang("backup_chatid_suc"))
        await sleep(2)
        await context.delete()
        return
    else:
        await context.edit(lang('backup_process'))
        await do_backup(context)
        await context.edit(lang("backup_success"))


async def do_backup(context=None):
    # Remove old backup
    if os.path.exists(pgm_backup_zip_name):
        os.remove(pgm_backup_zip_name)

    # backup redis when available
    redis_data = {}
    if redis_status():
        for k in redis.keys():
            data_type = redis.type(k)
            if data_type == b'string':
                v = redis.get(k)
                redis_data[k.decode()] = v.decode()

        with open(f"data{os.sep}redis.json", "w", encoding='utf-8') as f:
            json.dump(redis_data, f, indent=4)

    # run backup function
    exclude_filetypes = [".mp3", ".jpg", ".png", ".flac", ".ogg"] + pgm_backup_exclude_filetypes
    backup_files = ["data", "plugins", "config.yml", "docker-compose.yml", "dump.rdb", "redis.conf", "redis.conf.bak"]
    if strtobool(config['log']):
        now = datetime.now().date()
        file_path = f'pagermaid_backup_{now}.tar.gz'
        make_tar_gz(file_path, backup_files, exclude_filetypes)
        if context:
            await context.edit(lang("backup_uploading"))
        await upload_attachment(file_path, pgm_backup_chatid, None, caption=file_path)
        os.remove(file_path)
        if context:
            await context.edit(lang("backup_success_channel"))
    else:
        make_tar_gz("pagermaid_backup.tar.gz", backup_files, exclude_filetypes)


@listener(is_plugin=True, outgoing=True, command=alias_command("recovery"),
          description=lang('recovery_des'))
async def recovery(context):
    message = await context.get_reply_message()

    if message and message.media:  # Overwrite local backup
        if isinstance(message.media, MessageMediaDocument):
            try:
                if message.media.document.attributes[0].file_name.find(".tar.gz") != -1:  # Verify filename
                    await context.edit(lang('recovery_down'))
                    # Start download process
                    _file = BytesIO()
                    await context.client.download_file(message.media.document, _file)
                    with open(pgm_backup_zip_name, "wb") as f:
                        f.write(_file.getvalue())
                else:
                    return await context.edit(lang('recovery_file_error'))
            except Exception as e:  # noqa
                print(e, format_exc())
                return await context.edit(lang('recovery_file_error'))
        else:
            return await context.edit(lang('recovery_file_error'))

    # Extract backup files
    await context.edit(lang('recovery_process'))
    if not os.path.exists(pgm_backup_zip_name):
        return await context.edit(lang('recovery_file_not_found'))
    elif not un_tar_gz(pgm_backup_zip_name, ""):
        os.remove(pgm_backup_zip_name)
        return await context.edit(lang('recovery_file_error'))

    # Recovery redis
    if redis_status() and os.path.exists(f"data{os.sep}redis.json"):
        with open(f"data{os.sep}redis.json", "r", encoding='utf-8') as f:
            try:
                redis_data = json.load(f)
                for k, v in redis_data.items():
                    redis.set(k, v)
            except json.JSONDecodeError:
                """JSON load failed, skip redis recovery"""
            except Exception as e:  # noqa
                print(e, format_exc())

    # Cleanup
    if os.path.exists(pgm_backup_zip_name):
        os.remove(pgm_backup_zip_name)
    if os.path.exists(f"data{os.sep}redis.json"):
        os.remove(f"data{os.sep}redis.json")

    result = await context.edit(lang('recovery_success') + " " + lang('apt_reboot'))
    if redis_status():
        redis.set("restart_edit", f"{result.id}|{result.chat_id}")
    await context.client.disconnect()
