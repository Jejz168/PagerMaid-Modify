from telethon.tl.types.messages import ChatFull
from telethon.tl.types.users import UserFull

from pagermaid import log, redis, redis_status, user_id as self_user_id, bot, logs
from pagermaid.listener import listener
from pagermaid.utils import lang, alias_command
from struct import error as StructError
from telethon.tl.functions.messages import GetCommonChatsRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.functions.channels import DeleteParticipantHistoryRequest, EditBannedRequest
from telethon.tl.types import MessageEntityMentionName, ChannelParticipantsAdmins, MessageEntityPhone, PeerChannel, \
    ChatBannedRights, MessageEntityCode, Channel, PeerUser
from telethon.errors.rpcerrorlist import UserAdminInvalidError, ChatAdminRequiredError, FloodWaitError
from asyncio import sleep
from random import uniform


async def get_peer(object_n):
    if isinstance(object_n, Channel):
        full_chat = (await bot(GetFullChannelRequest(object_n.id)))  # noqa
        return full_chat.full_chat, full_chat
    elif isinstance(object_n, PeerUser):
        full_user = (await bot(GetFullUserRequest(object_n.user_id)))  # noqa
        return full_user.full_user, full_user
    else:
        full_user = (await bot(GetFullUserRequest(object_n.id)))
        return full_user.full_user, full_user


def mention_user(user):
    try:
        if isinstance(user, UserFull):
            first_name = user.users[0].first_name
            last_name = user.users[0].last_name
            user_id = user.full_user.id
        elif isinstance(user, ChatFull):
            first_name = user.users[0].first_name
            last_name = user.users[0].last_name
            user_id = user.full_chat.id
        else:
            first_name = user.first_name
            last_name = user.last_name
            user_id = user.id
    except Exception as e: # noqa
        logs.debug(f'mention user exception: {e}, user: {user}')
        first_name = ''
        last_name = ''
        user_id = ""
    first_name = first_name.replace("\u2060", "") if first_name else ''
    last_name = last_name.replace("\u2060", "") if last_name else ''
    full_name = f'{first_name} {last_name}'
    if full_name == " ":
        full_name = '×'
    return f'[{full_name}](tg://user?id={user_id})'


def mention_group(chat):
    try:
        if chat.username:
            if chat.username:
                text = f'[{chat.title}](https://t.me/{chat.username})'
            else:
                text = f'`{chat.title}`'
        else:
            text = f'`{chat.title}`'
    except AttributeError:
        text = f'`{chat.title}`'
    return text


@listener(is_plugin=False, outgoing=True,
          command=alias_command("sb"),
          description=lang('sb_des'),
          parameters="<reply|id|username> <do_not_del_all>")
async def span_ban(context):
    if context.reply_to_msg_id:
        reply_message = await context.get_reply_message()
        if reply_message:
            try:
                user = reply_message.from_id
            except AttributeError:
                await context.edit(lang('arg_error'))
                return
        else:
            await context.edit(lang('arg_error'))
            return
        if isinstance(user, PeerChannel):
            # 封禁频道
            try:
                entity = await context.client.get_input_entity(context.chat_id)
                user = await context.client.get_input_entity(reply_message.sender.id)
                await context.client(EditBannedRequest(
                    channel=entity,
                    participant=user,
                    banned_rights=ChatBannedRights(
                        until_date=None, view_messages=True)
                ))
            except ChatAdminRequiredError:
                return await context.edit(lang('sb_no_per'))
            return await context.edit(lang('sb_channel'))
        elif not user:
            return await context.edit(lang('arg_error'))
        target_user = user
    else:
        if len(context.parameter) == 1:
            user = context.parameter[0].strip("`")
            if user.isnumeric():
                user = int(user)
                if user < 0:
                    return await context.edit(lang('arg_error'))
        else:
            return await context.edit(lang('arg_error'))
        if context.message.entities is not None:
            if isinstance(context.message.entities[0], MessageEntityMentionName):
                user = context.message.entities[0].user_id
            elif isinstance(context.message.entities[0], MessageEntityPhone):
                user = int(context.parameter[0])
            elif isinstance(context.message.entities[0], MessageEntityCode):
                pass
            else:
                return await context.edit(f"{lang('error_prefix')}{lang('arg_error')}")
        try:
            user_object = await context.client.get_entity(user)
            target_user = user_object
        except (TypeError, ValueError, OverflowError, StructError) as exception:
            if str(exception).startswith("Cannot find any entity corresponding to"):
                await context.edit(f"{lang('error_prefix')}{lang('profile_e_no')}")
                return
            if str(exception).startswith("No user has"):
                await context.edit(f"{lang('error_prefix')}{lang('profile_e_nou')}")
                return
            if str(exception).startswith("Could not find the input entity for") or isinstance(exception, StructError):
                await context.edit(f"{lang('error_prefix')}{lang('profile_e_nof')}")
                return
            if isinstance(exception, OverflowError):
                await context.edit(f"{lang('error_prefix')}{lang('profile_e_long')}")
                return
            raise exception
    chat = await context.get_chat()
    if len(context.parameter) == 0:
        try:
            await context.client(DeleteParticipantHistoryRequest(channel=chat, participant=target_user))
        except UserAdminInvalidError:
            pass
        except ChatAdminRequiredError:
            pass
    target_user_temp, full_temp = await get_peer(target_user)
    if target_user_temp.id == self_user_id:
        await context.edit(lang('arg_error'))
        return
    result = await context.client(GetCommonChatsRequest(user_id=target_user, max_id=0, limit=100))
    count = 0
    groups = []
    for i in result.chats:
        try:
            chat = await context.client.get_entity(i.id)
            if len(context.parameter) == 0:
                await context.client(DeleteParticipantHistoryRequest(channel=chat, participant=target_user))
            await context.client.edit_permissions(i.id, target_user, view_messages=False)
            groups.append(mention_group(i))
            count += 1
        except FloodWaitError as e:
            # Wait flood secs
            await context.edit(f'{lang("sb_pause")} {e.seconds + uniform(0.5, 1.0)} s.')
            try:
                await sleep(e.seconds + uniform(0.5, 1.0))
            except Exception as e:
                print(f"Wait flood error: {e}")
                return
        except UserAdminInvalidError:
            pass
        except ChatAdminRequiredError:
            pass
        except ValueError:
            pass
    if redis_status():
        sb_groups = redis.get('sb_groups')
        if sb_groups:
            sb_groups = sb_groups.decode()
            sb_groups = sb_groups.split('|')
            try:
                sb_groups.remove('')
            except ValueError:
                pass
        else:
            sb_groups = []
        for i in sb_groups:
            try:
                chat = await context.client.get_entity(int(i))
                if len(context.parameter) == 0:
                    await context.client(DeleteParticipantHistoryRequest(channel=chat, participant=target_user))
                await context.client.edit_permissions(chat, target_user, view_messages=False)
                groups.append(mention_group(chat))
                count += 1
            except FloodWaitError as e:
                # Wait flood secs
                await context.edit(f'{lang("sb_pause")} {e.seconds + uniform(0.5, 1.0)} s.')
                try:
                    await sleep(e.seconds + uniform(0.5, 1.0))
                except Exception as e:
                    print(f"Wait flood error: {e}")
                    return
            except UserAdminInvalidError:
                pass
            except ChatAdminRequiredError:
                pass
    if count == 0:
        text = f'{lang("sb_no")} {mention_user(full_temp)}'
    else:
        text = f'{lang("sb_per")} {count} {lang("sb_in")} {mention_user(full_temp)}'
    await context.edit(text)
    if len(groups) > 0:
        groups = f'\n{lang("sb_pro")}\n' + "\n".join(groups)
    else:
        groups = ''
    await log(f'{text}\nuid: `{target_user_temp.id}` {groups}')


@listener(is_plugin=False, outgoing=True, command=alias_command("sb_set"),
          description=lang('sb_des_auto'),
          parameters="<true|false|status>")
async def span_ban_set(context):
    """ Toggles sb of a group. """
    if not redis_status():
        await context.edit(f"{lang('error_prefix')}{lang('redis_dis')}")
        return
    if len(context.parameter) != 1:
        await context.edit(f"{lang('error_prefix')}{lang('arg_error')}")
        return
    if not context.is_group:
        await context.edit(lang('ghost_e_mark'))
        return
    admins = await context.client.get_participants(context.chat, filter=ChannelParticipantsAdmins)
    if context.sender in admins:
        user = admins[admins.index(context.sender)]
        if not user.participant.admin_rights.ban_users:
            await context.edit(lang('sb_no_per'))
            return
    else:
        await context.edit(lang('sb_no_per'))
        return
    groups = redis.get('sb_groups')
    if groups:
        groups = groups.decode()
        groups = groups.split('|')
        try:
            groups.remove('')
        except ValueError:
            pass
    else:
        groups = []
    if context.parameter[0] == "true":
        if str(context.chat_id) not in groups:
            groups.append(str(context.chat_id))
            groups = '|'.join(groups)
            redis.set('sb_groups', groups)
            await context.edit(f"ChatID {str(context.chat_id)} {lang('sb_set')}")
            await log(f"ChatID {str(context.chat_id)} {lang('sb_set')}")
        else:
            await context.edit(f"ChatID {str(context.chat_id)} {lang('sb_set')}")
    elif context.parameter[0] == "false":
        if str(context.chat_id) in groups:
            groups.remove(str(context.chat_id))
            groups = '|'.join(groups)
            redis.set('sb_groups', groups)
            await context.edit(f"ChatID {str(context.chat_id)} {lang('sb_remove')}")
            await log(f"ChatID {str(context.chat_id)} {lang('sb_remove')}")
        else:
            await context.edit(f"ChatID {str(context.chat_id)} {lang('sb_remove')}")
    elif context.parameter[0] == "status":
        if str(context.chat_id) in groups:
            await context.edit(lang('sb_exist'))
        else:
            await context.edit(lang('sb_no_exist'))
    else:
        await context.edit(f"{lang('error_prefix')}{lang('arg_error')}")
