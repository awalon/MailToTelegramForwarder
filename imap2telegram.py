#!/usr/bin/env python

import sys
import socket
import time
import logging
try:
    import configparser
    import argparse
    import telegram_send
    from email.header import Header, decode_header, make_header
    from imapclient import IMAPClient
    from imapclient import exceptions as imap_exceptions
except ImportError as error:
        logging.critical(error.__class__.__name__ + ": " + error.message)
        sys.exit(2)


"""
    imap2telegram - A small python script that fetches mails from remote IMAP server
                    and looks for new messages in the inbox folder. Messages in
                    IMAP inbox folder _will be deleted_ and forwarded to users Telegram
                    account. Make sure you have installed 'telegram-send' with a valid
                    config and configured bot.

    WARNING:        Messages in IMAP inbox will be marked as deleted after every fetch!
"""


__appname__ = "imap2telegram"
__version__ = "0.9.1"
__author__ = "Florian Paul Hoberg <florian [at] hoberg.ch> @florianpaulhoberg"


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
        logging.NOTSET: "<7 " + __appname__ + ": ",
    }

    def __init__(self, stream=sys.stdout):
        self.stream = stream
        logging.Handler.__init__(self)

    def emit(self, record):
        try:
            msg = self.PREFIX[record.levelno] + self.format(record) + "\n"
            self.stream.write(msg)
            self.stream.flush()
        except Exception:
            self.handleError(record)


def parse_config(cliargs):
    """
        Parse config file to obtain login credentials and
        address of remote mailserver and telegram-send config.
    """
    try:
        config = configparser.ConfigParser()
        config.read(cliargs.config)
        imap_user = config['Mail']['user']
        imap_password = config['Mail']['password']
        imap_server = config['Mail']['server']
        imap_refresh = config['Mail']['refresh']
        telegram_config = config['Telegram']['config']
        return imap_user, imap_password, imap_server, imap_refresh, telegram_config
    except configparser.NoSectionError:
        logging.critical("Error parsing config file: Section not found.")
        sys.exit(2)
    except configparser.ParsingError:
        logging.critical("Error parsing config file: Impossible to parse file.")
        sys.exit(2)
    except KeyError:
        logging.critical("Error parsing config file: Key/Value not found.")
        sys.exit(2)


def imap_login(imap_user, imap_password, imap_server):
    """
        Login to remote IMAP server.
    """
    try:
        server = IMAPClient(imap_server, use_uid=True)
        server.login(imap_user, imap_password)
        return server
    except socket.gaierror:
        logging.critical("Could not connect to IMAP server.")
        sys.exit(2)
    except imap_exceptions.LoginError:
        logging.critical("IMAP login failed. Wrong user or password.")        
        sys.exit(2)


def imap_fetch_mails(server):
    """
        Get subjects of new emails in inbox on remote
        IMAP server.
    """
    try:
        select_info = server.select_folder('INBOX')
        imap_messages = server.search()
        imap_message_subjects = []
        for msgid, data in server.fetch(imap_messages, ['ENVELOPE']).items():
            envelope = data[b'ENVELOPE']
            imap_message_subjects.append(envelope)
        return imap_message_subjects, imap_messages
    except imap_exceptions.ProtocolError:
        logging.critical("IMAP action failed. Protocol operation not possible.")
        sys.exit(2)


def imap_delete_mails(server, imap_messages):
    """
        Mark fetched mails as deleted on remote
        IMAP server to avoid re-messaging them.
    """
    try:
        server.delete_messages(imap_messages)
        server.expunge()
    except imap_exceptions.ProtocolError:
        logging.critical("IMAP action failed. Protocol operation not possible.")
        sys.exit(2)


def imap_logout(server):
    """
        Logout and close connection on remote
        IMAP server.
    """
    try:
        server.logout()
    except imap_exceptions.ProtocolError:
        logging.critical("IMAP action failed. Protocol operation not possible.")
        sys.exit(2)


def telegram_send_message(telegram_config, imap_message_subjects):
    """
        Send fetched subjects of emails over
        Telegram API to user.
    """
    try:
        for single_message in imap_message_subjects:
            message, encoding = decode_header(single_message.subject)[0]
            telegram_send.send(messages=[message], conf=telegram_config, parse_mode=None, disable_web_page_preview=False, files=None, images=None, captions=None, locations=None, timeout=30)
            logging.info("Telegram notification sent.")
    except:
        logging.critical("Failed to send Telegram message.")
        sys.exit(2)


def main():
    """
        Run the main program
    """
    root_logger = logging.getLogger()
    root_logger.setLevel("INFO")
    root_logger.addHandler(SystemdHandler())

    argparser = argparse.ArgumentParser(description='imap2telegram')
    argparser.add_argument('-c', '--config', type=str, help='Path to config file')
    cliargs = argparser.parse_args()

    if cliargs.config is None:
        logging.warning("Could not load config file.")
        sys.exit(2)

    imap_user, imap_password, imap_server, imap_refresh, telegram_config = parse_config(cliargs)

    # Keep polling
    while True:
        server = imap_login(imap_user, imap_password, imap_server)
        imap_message_subjects, imap_messages = imap_fetch_mails(server)
        imap_delete_mails(server, imap_messages)
        imap_logout(server)
        telegram_send_message(telegram_config, imap_message_subjects)
        time.sleep(float(imap_refresh))


main()
