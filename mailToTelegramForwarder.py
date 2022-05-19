#!/usr/bin/env python3
"""
        Fetch mails from IMAP server and forward them to Telegram Chat.
        Copyright (C) 2021  Awalon (https://github.com/awalon)

        This program is free software: you can redistribute it and/or modify
        it under the terms of the GNU General Public License as published by
        the Free Software Foundation, either version 3 of the License, or
        (at your option) any later version.

        This program is distributed in the hope that it will be useful,
        but WITHOUT ANY WARRANTY; without even the implied warranty of
        MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
        GNU General Public License for more details.

        You should have received a copy of the GNU General Public License
        along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""
try:
    import warnings
    import sys
    import re
    import unicodedata
    import html
    import socket
    import time
    import logging
    import configparser
    import argparse
    import imaplib2
    import email
    from email.header import Header, decode_header, make_header
    from enum import Enum
except ImportError as import_error:
    logging.critical(import_error.__class__.__name__ + ": " + import_error.args[0])
    sys.exit(2)

"""
    Mail2TelegramForwarder:
                    A python script that fetches mails from remote IMAP mail server
                    and forward body and/or attachments to Telegram chat/user.
                    
                    Based on great work done by:
                    https://github.com/florianpaulhoberg/IMAP2Telegram
                    https://github.com/angelos-se/IMAPBot 
"""

__appname__ = "Mail to Telegram Forwarder"
__version__ = "0.1.5"
__author__ = "Awalon (https://github.com/awalon)"

with warnings.catch_warnings(record=True) as w:
    # Cause all warnings to always be triggered.
    warnings.simplefilter("always")

    from telegram.utils import helpers
    import telegram

    # Ignore not supported warnings
    if len(w) > 0:
        if 'This is allowed but not supported by python-telegram-bot maintainers' in str(w[-1].message):
            w.remove(w[-1])


class Tool:
    def __init__(self,):
        pass

    @staticmethod
    def binary_to_string(value, **kwargs) -> str:
        encoding = kwargs.get('encoding')
        if not encoding:
            encoding = 'utf-8'
        if type(value) is bytes:
            try:
                return str(bytes.decode(value, encoding=encoding, errors='replace'))
            except UnicodeDecodeError as decode_error:
                logging.error("Can not decode value: '", value, "' reason: ", decode_error.reason)
                return ' ###decoder-error:%s### ' % decode_error.reason
        else:
            return str(value)

    @staticmethod
    def build_error_message(message):
        error_message = message
        if type(message) is not str:
            error_message = '%s' % message  # ', '.join(map(str, message.args))
        try:
            exc_type, exc_obj, tb = sys.exc_info()
            line_no = ''
            obj_name = ''
            file_name = ''
            if tb is not None:
                frame = tb.tb_frame
                line_no = tb.tb_lineno
                obj_name = frame.f_code.co_name
                file_name = frame.f_code.co_filename
            trace_msg = " [%s:%s in '%s']" % (file_name, line_no, obj_name)
            error_message = '%s%s' % (error_message, trace_msg)
        except Exception as ex:
            logging.error('Fatal in "build_error_message": %s' % str(ex))
            logging.error('--- initial error: "%s"' % message)
        return error_message


class Config:
    config = None

    imap_user = None
    imap_password = None
    imap_server = None
    imap_port = 993
    imap_timeout = 60
    imap_refresh = 10
    imap_push_mode = False
    imap_disconnect = False
    imap_folder = 'INBOX'
    imap_search = '(UID ${lastUID}:* UNSEEN)'
    imap_mark_as_read = False
    imap_max_length = 2000
    imap_read_old_mails = False
    imap_read_old_mails_processed = False

    tg_bot_token = None
    tg_forward_to_chat_id = None
    tg_prefer_html = True
    tg_markdown_version = 2
    tg_forward_mail_content = True
    tg_forward_attachment = True
    tg_forward_embedded_images = True

    def __init__(self, cmd_args):
        """
            Parse config file to obtain login credentials, address of remote mail server,
            telegram config and configuration which controls behaviour of this script .
        """
        try:
            self.config = configparser.ConfigParser()
            files = self.config.read(cmd_args.config)
            if len(files) == 0:
                logging.critical("Error parsing config file: File '%s' not found!" % cmd_args.config)
                sys.exit(2)

            self.imap_user = self.get_config('Mail', 'user', self.imap_user)
            self.imap_password = self.get_config('Mail', 'password', self.imap_password)
            self.imap_server = self.get_config('Mail', 'server', self.imap_server)
            self.imap_port = self.get_config('Mail', 'port', self.imap_port, int)
            self.imap_timeout = self.get_config('Mail', 'timeout', self.imap_timeout, int)
            self.imap_refresh = self.get_config('Mail', 'refresh', self.imap_refresh, int)
            self.imap_push_mode = self.get_config('Mail', 'push_mode', self.imap_push_mode, bool)
            self.imap_disconnect = self.get_config('Mail', 'disconnect', self.imap_disconnect, bool)
            self.imap_folder = self.get_config('Mail', 'folder', self.imap_folder)
            self.imap_read_old_mails = self.get_config('Mail', 'read_old_mails', self.imap_read_old_mails)
            self.imap_search = self.get_config('Mail', 'search', self.imap_search)
            self.imap_mark_as_read = self.get_config('Mail', 'mark_as_read', self.imap_mark_as_read, bool)
            self.imap_max_length = self.get_config('Mail', 'max_length', self.imap_max_length, int)

            self.tg_bot_token = self.get_config('Telegram', 'bot_token', self.tg_bot_token)
            self.tg_forward_to_chat_id = self.get_config('Telegram', 'forward_to_chat_id',
                                                         self.tg_forward_to_chat_id, int)
            self.tg_forward_mail_content = self.get_config('Telegram', 'forward_mail_content',
                                                           self.tg_forward_mail_content, bool)
            self.tg_prefer_html = self.get_config('Telegram', 'prefer_html', self.tg_prefer_html, bool)
            self.tg_markdown_version = self.get_config('Telegram', 'markdown_version', self.tg_markdown_version, int)
            self.tg_forward_attachment = self.get_config('Telegram', 'forward_attachment',
                                                         self.tg_forward_attachment, bool)
            self.tg_forward_embedded_images = self.get_config('Telegram', 'forward_embedded_images',
                                                              self.tg_forward_embedded_images, bool)
            if cmd_args.read_old_mails:
                self.imap_read_old_mails = True

        except configparser.ParsingError as parse_error:
            logging.critical(Tool.build_error_message(
                "Error parsing config file: Impossible to parse file %s. Message: %s"
                % (parse_error.source, parse_error.message))
            )
            sys.exit(2)
        except configparser.Error as config_error:
            logging.critical(Tool.build_error_message("Error parsing config file: %s." % config_error.message))
            sys.exit(2)

    def get_config(self, section, key, default=None, value_type=None):
        value = default
        try:
            if self.config.has_section(section):
                if self.config.has_option(section, key):
                    if value_type is not None:
                        # get value based on type of default value
                        if value_type is int:
                            value = self.config.getint(section, key)
                        elif value_type is float:
                            value = self.config.getfloat(section, key)
                        elif value_type is bool:
                            value = self.config.getboolean(section, key)
                        else:
                            value = self.config.get(section, key)
                    else:
                        # use string as default
                        value = self.config.get(section, key)
            else:
                # raise exception as both sections are mandatory sections (Mail + Telegram)
                logging.warning("Get config value error for '%s'.'%s' (default: '%s'): Missing section '%s'."
                                % (section, key, default, section))
                raise configparser.NoSectionError(section)

        except configparser.Error as config_error:
            logging.critical(Tool.build_error_message("Error parsing config file: %s." % config_error.message))
            raise config_error
        except Exception as get_val_error:
            logging.critical(Tool.build_error_message(
                "Get config value error for '%s'.'%s' (default: '%s'): %s."
                % (section, key, default, get_val_error))
            )
            raise get_val_error

        return value


class MailAttachmentType(Enum):
    BINARY = 1
    IMAGE = 2


class MailAttachment:
    idx = 0
    id = ''
    name = ''
    alt = ''
    type = MailAttachmentType.BINARY
    file = None
    tg_id = None

    def __init__(self, attachment_type=MailAttachmentType.BINARY):
        self.type = attachment_type

    def set_name(self, file_name):
        name = ''
        for file_name_part in email.header.decode_header(file_name):
            part, encoding = file_name_part
            name += Tool.binary_to_string(part, encoding=encoding)
        self.name = name

    def set_id(self, attachment_id):
        self.id = re.sub(r'[<>]', '', attachment_id)

    def get_title(self):
        if self.alt:
            return self.alt
        elif self.name:
            return self.name
        else:
            return self.file


class MailBody:
    text = ''
    html = ''
    images: dict[str, MailAttachment] = {}
    attachments: [MailAttachment] = []


class MailData:
    TEXT = 1
    HTML = 2

    uid = ''
    raw = ''
    type = TEXT
    summary = ''
    mail_from = ''
    mail_subject = ''
    mail_body = ''
    mail_images: dict[str, MailAttachment] = {}
    attachment_summary = ''
    attachments = [MailAttachment]


class TelegramBot:
    config: Config = None

    def __init__(self, config):
        self.config = config

    @staticmethod
    def cleanup_html(message: str, images: dict[str, MailAttachment] = None) -> str:
        """
        Parse HTML message and remove HTML elements not supported by Telegram
        """
        # supported tags
        # https://core.telegram.org/bots/api#sendmessage
        # <b>bold</b>, <strong>bold</strong>
        # <i>italic</i>, <em>italic</em>
        # <u>underline</u>, <ins>underline</ins>
        # <s>strikethrough</s>, <strike>strikethrough</strike>, <del>strikethrough</del>
        # <b>bold <i>italic bold <s>italic bold strikethrough</s> <u>underline italic bold</u></i> bold</b>
        # <a href="http://www.example.com/">inline URL</a>
        # <a href="tg://user?id=123456789">inline mention of a user</a>
        # <code>inline fixed-width code</code>
        # <pre>pre-formatted fixed-width code block</pre>
        # <pre><code class="language-python">pre-formatted fixed-width code block
        #      written in the Python programming language</code></pre>

        tg_body = message
        tg_msg = ''
        try:
            # extract HTML body to get payload from mail
            tg_body = re.sub('.*<body[^>]*>(?P<body>.*)</body>.*$', '\g<body>', tg_body,
                             flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove control chars
            tg_body = "".join(ch for ch in tg_body if "C" != unicodedata.category(ch)[0])

            # remove all HTML comments
            tg_body = re.sub(r'<!--.*?-->', '', tg_body, flags=(re.DOTALL | re.MULTILINE))

            # handle inline images
            image_seen = {}
            for match in re.finditer(r'(?P<img><\s*img\s+[^>]*?\s*src\s*=\s*"cid:(?P<cid>[^"]*)"[^>]*?/?\s*>)',
                                     tg_body, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE)):
                img = match.group('img')
                cid = match.group('cid')
                if cid == '' or cid in image_seen:
                    continue
                image_seen[cid] = True

                alt = re.sub(r'^.*?((title|alt)\s*=\s*"(?P<alt>[^"]+)")?.*?$', '\g<alt>',
                             img, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))
                if cid in images:
                    # add image reference
                    tg_body = tg_body.replace(img, '${file:%s}' % cid)
                    # extract alt/title attributes of img elements
                    images[cid].alt = alt
                else:
                    # no file found, use alt text
                    tg_body = tg_body.replace(img, alt)

            # use alt text for all images without cid (embedded image)
            tg_body = re.sub(r'<\s*img\s+[^>]*?((title|alt)\s*=\s*"(?P<alt>[^"]+)")?[^>]*?/?\s*>', '\g<alt>',
                             tg_body, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove multiple line breaks and spaces (regular Browser logic)
            tg_body = re.sub(r'[\r\n]', '', tg_body)
            tg_body = re.sub(r'\s\s+', ' ', tg_body).strip()

            # remove attributes from elements but href of "a"- elements
            tg_msg = re.sub(r'<\s*?(?P<elem>\w+)\b\s*?[^>]*?(?P<ref>\s+href\s*=\s*"[^"]+")?[^>]*?>',
                            '<\g<elem>\g<ref>>', tg_body, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove style and script elements/blocks
            tg_msg = re.sub(r'<\s*(?P<elem>script|style)\s*>.*?</\s*(?P=elem)\s*>',
                            '', tg_msg, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # preserve NBSPs
            tg_msg = re.sub(r'&nbsp;', ' ', tg_msg, flags=re.IGNORECASE)

            # translate paragraphs and line breaks (block elements)
            tg_msg = re.sub(r'</?\s*(?P<elem>(p|div|table|h\d+))\s*>', '\n', tg_msg,
                            flags=(re.MULTILINE | re.IGNORECASE))
            tg_msg = re.sub(r'</\s*(?P<elem>(tr))\s*>', '\n', tg_msg, flags=(re.MULTILINE | re.IGNORECASE))
            tg_msg = re.sub(r'</?\s*(br)\s*[^>]*>', '\n', tg_msg, flags=(re.MULTILINE | re.IGNORECASE))

            # prepare list items (migrate list items to "- <text of li element>")
            tg_msg = re.sub(r'(<\s*[ou]l\s*>[^<]*)?<\s*li\s*>', '\n- ', tg_msg, flags=(re.MULTILINE | re.IGNORECASE))
            tg_msg = re.sub(r'</\s*li\s*>([^<]*</\s*[ou]l\s*>)?', '\n', tg_msg, flags=(re.MULTILINE | re.IGNORECASE))

            # remove unsupported tags
            regex_filter_elem = re.compile('<\s*(?!/?(bold|strong|i|em|u|ins|s|strike|del|b|a|code|pre))\s*[^>]*?>',
                                           flags=re.MULTILINE)
            tg_msg = re.sub(regex_filter_elem, ' ', tg_msg)
            tg_msg = re.sub(r'</?\s*(img|span)\s*[^>]*>', '', tg_msg, flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove empty links
            tg_msg = re.sub(r'<\s*a\s*>(?P<link>[^<]*)</\s*a\s*>', '\g<link> ', tg_msg,
                            flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove links without text (tracking stuff, and none clickable)
            tg_msg = re.sub(r'<\s*a\s*[^>]*>\s*</\s*a\s*>', ' ', tg_msg,
                            flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE))

            # remove empty elements
            tg_msg = re.sub(r'<\s*\w\s*>\s*</\s*\w\s*>', ' ', tg_msg, flags=(re.DOTALL | re.MULTILINE))

        except Exception as ex:
            logging.critical(Tool.build_error_message(ex))

        finally:
            return tg_msg

    def send_message(self, mails: [MailData]):
        """
        Send mail data over Telegram API to chat/user.
        """
        try:
            bot: telegram.Bot = telegram.Bot(self.config.tg_bot_token)
            tg_chat: telegram.Chat = bot.get_chat(self.config.tg_forward_to_chat_id)

            # get chat title
            tg_chat_title = tg_chat.full_name
            if not tg_chat_title:
                tg_chat_title = tg_chat.title
            if not tg_chat_title:
                tg_chat_title = tg_chat.description

            for mail in mails:
                try:
                    if self.config.tg_markdown_version == 2:
                        parser = telegram.ParseMode.MARKDOWN_V2
                    else:
                        parser = telegram.ParseMode.MARKDOWN
                    if mail.type == MailData.HTML:
                        parser = telegram.ParseMode.HTML

                    if self.config.tg_forward_mail_content or not self.config.tg_forward_attachment:
                        # send mail content (summary)
                        message = mail.summary

                        # upload images
                        image_no = 1
                        for image_id in mail.mail_images:
                            image = mail.mail_images[image_id]
                            title = '%s' % image.get_title()

                            if self.config.tg_forward_embedded_images:
                                title = '%i. %s: %s' % (image_no, mail.mail_subject, image.get_title())
                                doc_message: telegram.Message = bot.send_photo(
                                    chat_id=self.config.tg_forward_to_chat_id,
                                    parse_mode=parser,
                                    caption=title,
                                    photo=image.file,
                                )
                                photo_size: [telegram.PhotoSize] = doc_message.photo
                                image.tg_id = photo_size[0].file_id
                                # image.tg_id = doc_message.caption

                            message = message.replace(
                                '${file:%s}' % image.id,
                                '🖼 %s' % title
                            )
                            image_no += 1

                        tg_message = bot.send_message(chat_id=self.config.tg_forward_to_chat_id,
                                                      parse_mode=parser,
                                                      text=message,
                                                      disable_web_page_preview=False)

                        logging.info("Mail summary for '%s' was sent with ID '%i' to '%s' (ID: '%i')"
                                     % (mail.mail_subject, tg_message.message_id,
                                        tg_chat_title, self.config.tg_forward_to_chat_id))

                    if self.config.tg_forward_attachment and len(mail.attachments) > 0:
                        for attachment in mail.attachments:
                            subject = mail.mail_subject
                            if mail.type == MailData.HTML:
                                file_name = attachment.name
                                caption = '<b>' + subject + '</b>:\n' + file_name
                            else:
                                file_name = telegram.utils.helpers.escape_markdown(
                                    text=attachment.name, version=self.config.tg_markdown_version)
                                caption = '*' + subject + '*:\n' + file_name

                            tg_message = bot.send_document(chat_id=self.config.tg_forward_to_chat_id,
                                                           parse_mode=parser,
                                                           caption=caption,
                                                           document=attachment.file,
                                                           filename=attachment.name,
                                                           disable_content_type_detection=False)

                            logging.info("Attachment '%s' was sent with ID '%i' to '%s' (ID: '%s')"
                                         % (attachment.name, tg_message.message_id,
                                            tg_chat_title, str(self.config.tg_forward_to_chat_id)))

                except telegram.TelegramError as tg_mail_error:
                    msg = "❌ Failed to send Telegram message (UID: %s) to '%s': %s" \
                          % (mail.uid, str(self.config.tg_forward_to_chat_id), tg_mail_error.message)
                    logging.critical(Tool.build_error_message(msg))
                    try:
                        # try to send error via telegram, and ignore further errors
                        bot.send_message(chat_id=self.config.tg_forward_to_chat_id,
                                         parse_mode=telegram.ParseMode.MARKDOWN_V2,
                                         text=telegram.utils.helpers.escape_markdown(msg, version=2),
                                         disable_web_page_preview=False)
                    finally:
                        pass
                    pass

                except Exception as send_mail_error:
                    error_msgs = [Tool.binary_to_string(arg) for arg in send_mail_error.args]
                    msg = "Failed to send Telegram message (UID: %s) to '%s': %s"\
                          % (mail.uid, str(self.config.tg_forward_to_chat_id), ', '.join(error_msgs))
                    logging.critical(Tool.build_error_message(msg))
                    try:
                        # try to send error via telegram, and ignore further errors
                        bot.send_message(chat_id=self.config.tg_forward_to_chat_id,
                                         parse_mode=telegram.ParseMode.MARKDOWN_V2,
                                         text=telegram.utils.helpers.escape_markdown(msg, version=2),
                                         disable_web_page_preview=False)
                    finally:
                        pass
                    pass

        except telegram.TelegramError as tg_error:
            logging.critical(Tool.build_error_message("Failed to send Telegram message: %s" % tg_error.message))
            return False

        except Exception as send_error:
            error_msgs = [Tool.binary_to_string(arg) for arg in send_error.args]
            logging.critical(Tool.build_error_message("Failed to send Telegram message: %s" % ', '.join(error_msgs)))
            return False

        return True


class Mail:
    mailbox: imaplib2.IMAP4_SSL = None
    config: Config = None
    last_uid: str = ''

    previous_error = None

    class MailError(Exception):
        def __init__(self, message, errors=None):
            super().__init__(message)
            self.errors = errors

    def __init__(self, config):
        """
        Login to remote IMAP server.
        """
        self.config = config
        try:
            self.mailbox = imaplib2.IMAP4_SSL(host=config.imap_server,
                                              port=config.imap_port,
                                              timeout=config.imap_timeout)
            rv, data = self.mailbox.login(config.imap_user, config.imap_password)
            if rv != 'OK':
                msg = "Cannot login to mailbox: %s" % str(rv)
                raise self.MailError(msg)

        except socket.gaierror as gai_error:
            msg = "Connection error '%s:%i': %s" % (config.imap_server,
                                                    config.imap_port,
                                                    gai_error.strerror)
            logging.debug(msg)
            raise self.MailError(msg, gai_error)

        except imaplib2.IMAP4_SSL.error as imap_ssl_error:
            error_msgs = [Tool.binary_to_string(arg) for arg in imap_ssl_error.args]
            msg = "Login to '%s:%i' failed: %s" % (config.imap_server,
                                                   config.imap_port,
                                                   ', '.join(error_msgs))
            logging.debug(msg)
            raise self.MailError(msg, imap_ssl_error)

        except Exception as login_error:
            msg = "Mail error during connection to '%s:%i' failed: %s" \
                  % (config.imap_server, config.imap_port, ', '.join(map(str, login_error.args)))
            logging.debug(msg)
            raise self.MailError(msg, login_error)

        rv, mailboxes = self.mailbox.list()
        if rv != 'OK':
            self.disconnect()
            msg = "Can't get list of available mailboxes / folders: %s" % str(rv)
            raise self.MailError(msg)
        else:
            logging.info("Mailboxes:")
            logging.info(mailboxes)

        rv, data = self.mailbox.select(config.imap_folder)
        if rv == 'OK':
            logging.info("Processing mailbox...")
        else:
            msg = "ERROR: Unable to open mailbox: %s" % str(rv)
            logging.debug(msg)
            raise self.MailError(msg)

    def is_connected(self):
        if self.mailbox is not None:
            try:
                rv, data = self.mailbox.noop()
                if rv == 'OK':
                    logging.debug("Connection is working...")
                    return True
            except Exception as connection_check_error:
                msg = "Error during connection check [noop]: %s" \
                      % (', '.join(map(str, connection_check_error.args)))
                logging.error(msg)
                pass
        return False

    def disconnect(self):
        if self.mailbox is not None:
            try:
                self.mailbox.close()
                self.mailbox.logout()
            except Exception as ex:
                logging.debug("Cannot close mailbox: %s" % ', '.join(ex.args))
                pass
            finally:
                del self.mailbox

    @staticmethod
    def decode_body(msg) -> MailBody:
        """
        Get payload from message and return structured body data
        """
        html_part = None
        text_part = None
        attachments: [MailAttachment] = []
        images: dict[str, MailAttachment] = {}
        index: int = 1

        for part in msg.walk():
            if part.get_content_type().startswith('multipart/'):
                continue

            elif part.get_content_type() == 'text/plain':
                # extract plain text body
                text_part = part.get_payload(decode=True)
                encoding = part.get_content_charset()
                if not encoding:
                    encoding = 'utf-8'
                text_part = bytes(text_part).decode(encoding).strip()

            elif part.get_content_type() == 'text/html':
                # extract HTML body
                html_part = part.get_payload(decode=True)
                encoding = part.get_content_charset()
                if not encoding:
                    encoding = 'utf-8'
                html_part = bytes(html_part).decode(encoding).strip()

            elif part.get_content_type() == 'message/rfc822':
                continue

            elif part.get_content_type() == 'text/calendar':
                # extract calendar/appointment files
                attachment = MailAttachment()
                attachment.idx = index
                attachment.name = 'invite.ics'
                attachment.file = part.get_payload(decode=True)
                attachments.append(attachment)
                index += 1

            elif part.get_content_charset() is None:
                if part.get_content_disposition() == 'attachment':
                    # extract attachments
                    attachment = MailAttachment()
                    attachment.idx = index
                    attachment.set_name(str(part.get_filename()))
                    attachment.file = part.get_payload(decode=True)
                    attachments.append(attachment)
                    index += 1

                elif part.get_content_disposition() == 'inline':
                    # extract inline images
                    if part.get_content_type() in ('image/png', 'image/jpeg'):
                        image = MailAttachment(MailAttachmentType.IMAGE)
                        image.idx = index
                        image.set_name(str(part.get_filename()))
                        image.set_id(part.get('Content-ID', image.name))
                        image.file = part.get_payload(decode=True)
                        images[image.id] = image
                        index += 1

        body = MailBody()
        body.text = text_part
        body.html = html_part
        body.attachments = attachments
        body.images = images
        return body

    def get_last_uid(self):
        """
        get UID of most recent mail
        """
        rv, data = self.mailbox.uid('search', '', 'UID *')
        if rv != 'OK':
            logging.info("No messages found!")
            return ''
        return Tool.binary_to_string(data[0])

    def parse_mail(self, uid, mail) -> (MailData, None):
        """
        parse data from mail like subject, body and attachments and return structured mail data
        """
        try:
            msg = email.message_from_bytes(mail)

            # decode body data (text, html, multipart/attachments)
            body = self.decode_body(msg)
            message_type = MailData.TEXT
            content = ''

            if self.config.tg_forward_mail_content:
                # remove useless content
                if body.text:
                    content = body.text.replace('()', '').replace('[]', '').strip()

                    # insert inline image
                    if self.config.tg_forward_embedded_images:
                        for cid in re.finditer(r'\[cid:([^]]*)]', content,
                                               flags=(re.DOTALL | re.MULTILINE | re.IGNORECASE)):
                            if cid in body.images:
                                content = content.replace(
                                    '[cid:' + cid.string + ']',
                                    '${file:' + body.images[cid.string].tg_id + '}'
                                )

                if self.config.tg_prefer_html:
                    # Prefer HTML
                    if body.html:
                        message_type = MailData.HTML
                        content = TelegramBot.cleanup_html(body.html, body.images)

                    elif body.text:
                        content = telegram.utils.helpers.escape_markdown(text=content,
                                                                         version=self.config.tg_markdown_version)

                else:
                    if body.text:
                        content = telegram.utils.helpers.escape_markdown(text=content,
                                                                         version=self.config.tg_markdown_version)

                    elif body.html:
                        message_type = MailData.HTML
                        content = TelegramBot.cleanup_html(body.html, body.images)

                if content:
                    # remove multiple line breaks (keeping up to 1 empty line)
                    content = re.sub(r'(\s*\r?\n){2,}', "\n\n", content)

                    if message_type == MailData.HTML:
                        # add space after links (provide space for touch on link lists)
                        # '&lt;' keep mail marker together (ex.: &lt;<a href="mailto:t@ex.com">t@ex.xom</a>&gt;)
                        content = re.sub(r'(?P<a></a>(\s*&gt;)?)\s*', '\g<a>\n\n', content, flags=re.MULTILINE)

                    # remove spaces and line breaks on start and end (enhanced strip)
                    content = re.sub(r'^[\s\n]*', '', content)
                    content = re.sub(r'[\s\n]*$', '', content)

                    max_len = self.config.imap_max_length
                    content_len = len(content)
                    if message_type == MailData.HTML and content_len > 0:
                        # get length from parsed HTML (all tags removed)
                        content_plain = re.sub(r'<[^>]*>', '', content, flags=re.MULTILINE)
                        # get new max length based on plain text factor
                        plain_factor = (len(content_plain) / content_len) + float(1)
                        max_len = int(max_len * plain_factor)
                    if content_len > max_len:
                        content = content[:max_len]
                        if message_type == MailData.HTML:
                            # remove incomplete html tag
                            content = re.sub(r'<(\s*\w*(\s*[^>]*?)?(</[^>]*)?)?$', '', content)
                        else:
                            # remove last "\"
                            content = re.sub(r'\\*$', '', content)
                        content += "... (first " + str(max_len) + " characters)"

            # attachment summary
            attachments_summary = ""
            if body.attachments:
                if message_type == MailData.HTML:
                    attachments_summary = "\n\n" + chr(10133) + \
                                          " <b>" + str(len(body.attachments)) + " attachments:</b>\n"
                else:
                    attachments_summary = "\n\n" + chr(10133) + \
                                          " **" + str(len(body.attachments)) + " attachments:**\n"
                for attachment in body.attachments:
                    if message_type == MailData.HTML:
                        file_name = attachment.name
                    else:
                        file_name = telegram.utils.helpers.escape_markdown(
                            text=attachment.name, version=self.config.tg_markdown_version)
                    attachments_summary += "\n " + str(attachment.idx) + ": " + file_name

            # subject
            subject = ''
            for subject_part in email.header.decode_header(msg['Subject']):
                part, encoding = subject_part
                subject += Tool.binary_to_string(part, encoding=encoding)

            # build summary
            mail_from = Tool.binary_to_string(msg['From'])
            if self.config.tg_forward_mail_content:
                summary_line = "\n=============================\n"
            else:
                summary_line = "\n"

            if message_type == MailData.HTML:
                mail_from = html.escape(mail_from, quote=True)
                email_text = "<b>From:</b> " + mail_from + "\n<b>Subject:</b> "
            else:
                subject = telegram.utils.helpers.escape_markdown(text=subject,
                                                                 version=self.config.tg_markdown_version)
                mail_from = telegram.utils.helpers.escape_markdown(text=mail_from,
                                                                   version=self.config.tg_markdown_version)
                summary_line = telegram.utils.helpers.escape_markdown(text=summary_line,
                                                                      version=self.config.tg_markdown_version)
                email_text = "*From:* " + mail_from + "\n*Subject:* "
            email_text += subject + summary_line + content + " " + attachments_summary

            mail_data = MailData()
            mail_data.uid = uid
            mail_data.raw = msg
            mail_data.type = message_type
            mail_data.mail_from = mail_from
            mail_data.mail_subject = subject
            mail_data.mail_body = content
            mail_data.mail_images = body.images
            mail_data.summary = email_text
            mail_data.attachment_summary = attachments_summary
            mail_data.attachments = body.attachments

            return mail_data

        except Exception as parse_error:
            if len(parse_error.args) > 0:
                logging.critical(Tool.build_error_message("Cannot process mail: %s" % parse_error.args[0]))
            else:
                logging.critical(Tool.build_error_message("Cannot process mail: %s" % parse_error.__str__()))
            return None

    def search_mails(self) -> [MailData]:
        """
        Search mail on remote IMAP server and return list of parsed mails.
        """
        if self.last_uid is None or self.last_uid == '':
            self.last_uid = self.get_last_uid()
            logging.info("Most recent UID: %s" % self.last_uid)

        # build IMAP search string
        search_string = self.config.imap_search
        if not search_string:
            "(UID " + str(self.last_uid) + ":*)"
        else:
            search_string = re.sub(r'\${lastUID}', str(self.last_uid), search_string)

        if re.match(r'.*\bUID\b\s*:.*', search_string) and self.last_uid == '':
            # empty mailbox
            return

        try:
            rv, data = self.mailbox.uid('search', '', search_string)
            if rv != 'OK':
                logging.info("No messages found!")
                return

        except imaplib2.IMAP4_SSL.error as search_error:
            error_msgs = [Tool.binary_to_string(arg) for arg in search_error.args]
            msg = "Search with '%s' returned: %s" % (search_string, ', '.join(error_msgs))
            if msg != self.previous_error:
                logging.error(msg)
            self.previous_error = msg
            self.disconnect()
            raise self.MailError(msg)

        except Exception as search_ex:
            msg = ', '.join(map(str, search_ex.args))
            logging.critical(Tool.build_error_message("Cannot search mail: %s" % msg))
            self.disconnect()
            return self.MailError(msg)

        mails = []
        if self.config.imap_read_old_mails and not self.config.imap_read_old_mails_processed:
            # ignore current/max UID during first loop
            max_num = 0
            # don't repeat this on next loops
            self.config.imap_read_old_mails = False
            logging.info('Ignore max UID %s, as old mails have to be processed first...' % self.last_uid)
        else:
            max_num = int(self.last_uid)
            if not self.config.imap_read_old_mails_processed:
                self.config.imap_read_old_mails_processed = True
                logging.info('Reading mails having UID greater than %s...' % self.last_uid)

        for num in sorted(data[0].split()):
            current_uid = int(Tool.binary_to_string(num))

            if current_uid > max_num:
                try:
                    rv, data = self.mailbox.uid('fetch', num, '(RFC822)')
                    if rv != 'OK':
                        logging.error("ERROR getting message", num)
                        return

                    msg_raw = data[0][1]
                    mail = self.parse_mail(Tool.binary_to_string(num), msg_raw)
                    if mail is None:
                        logging.error("Can't parse mail with UID: %s" % num)
                    else:
                        mails.append(mail)

                except Exception as mail_error:
                    logging.critical(Tool.build_error_message("Cannot process mail: %s"
                                                              % ', '.join(map(str, mail_error.args))))

                finally:
                    # remember new UID for next loop
                    max_num = current_uid

        if len(mails) > 0:
            self.last_uid = str(max_num)
            logging.info("Got %i new mail(s) to forward, changed UID to %s" % (len(mails), self.last_uid))
        return mails


class SystemdHandler(logging.Handler):
    """
        Class to handle logging options.
    """
    PREFIX = {
        logging.CRITICAL: "<2> " + __appname__ + ": ",
        logging.ERROR: "<3> " + __appname__ + ": ",
        logging.WARNING: "<4> " + __appname__ + ": ",
        logging.INFO: "<6> " + __appname__ + ": ",
        logging.DEBUG: "<7> " + __appname__ + ": ",
        logging.NOTSET: "<7> " + __appname__ + ": ",
    }

    def __init__(self, stream=sys.stdout):
        self.stream = stream
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            msg = self.PREFIX[record.levelno] + self.format(record) + "\n"
            self.stream.write(msg)
            self.stream.flush()
        except Exception as emit_error:
            self.handleError(record)
            if len(emit_error.args) > 0:
                print("ERROR: SystemdHandler.emit failed with: " + emit_error.args[0])
            else:
                print("ERROR: SystemdHandler.emit failed with: " + emit_error.__str__())


def main():
    """
        Run the main program
    """
    root_logger = logging.getLogger()
    root_logger.setLevel("INFO")
    root_logger.addHandler(SystemdHandler())

    args_parser = argparse.ArgumentParser(description='Mail to Telegram Forwarder')
    args_parser.add_argument('-c', '--config', type=str, help='Path to config file', required=True)
    args_parser.add_argument('-o', '--read-old-mails', action='store_true', required=False,
                             help='Read mails received, before application was started')
    cmd_args = args_parser.parse_args()

    if cmd_args.config is None:
        logging.warning("Could not load config file, as no config file was provided.")
        sys.exit(2)

    mailbox = None
    try:
        config = Config(cmd_args)
        tg_bot = TelegramBot(config)
        mailbox = Mail(config)

        # Keep polling
        while True:
            try:
                if mailbox is None:
                    mailbox = Mail(config)
                else:
                    if not mailbox.is_connected():  # reconnect on error (broken connection)
                        mailbox = Mail(config)

                mails = mailbox.search_mails()

                if config.imap_disconnect:
                    # if not reuse previous connection
                    mailbox.disconnect()

                # send mail data via TG bot
                if mails is not None and len(mails) > 0:
                    tg_bot.send_message(mails)

                if config.imap_push_mode:
                    logging.info("IMAP IDLE mode")
                else:
                    time.sleep(float(config.imap_refresh))

            except Mail.MailError as mail_ex:
                if len(mail_ex.args) > 0:
                    logging.critical(Tool.build_error_message('Error occurred [mail]: %s'
                                                              % ', '.join(map(str, mail_ex.args))))
                else:
                    logging.critical(Tool.build_error_message('Error occurred [mail]: %s' % mail_ex.__str__()))

                if mailbox is not None:
                    mailbox.disconnect()

                # ignore errors already handled by Mail- Class
                pass

            except Exception as loop_error:
                if len(loop_error.args) > 0:
                    logging.critical(Tool.build_error_message('Error occurred [loop]: %s'
                                                              % ', '.join(map(str, loop_error.args))))
                else:
                    logging.critical(Tool.build_error_message('Error occurred [loop]: %s' % loop_error.__str__()))

                if mailbox is not None:
                    mailbox.disconnect()

    except KeyboardInterrupt:
        logging.critical('Stopping user aborted with CTRL+C')

    except Mail.MailError:  # ignore errors already handled by Mail- Class
        pass

    except Exception as main_error:
        if len(main_error.args) > 0:
            logging.critical(Tool.build_error_message('Error occurred [main]: %s'
                                                      % ', '.join(map(str, main_error.args))))
        else:
            logging.critical(Tool.build_error_message('Error occurred [main]: %s' % main_error.__str__()))

    finally:
        if mailbox is not None:
            mailbox.disconnect()
        logging.info('Mail to Telegram Forwarder stopped!')


main()
