# MailToTelegramForwarder - Service
[![GitHub issues](https://img.shields.io/github/issues/awalon/MailToTelegramForwarder?style=flat-square)](https://github.com/awalon/MailToTelegramForwarder/issues) 
![GitHub](https://img.shields.io/badge/version-3-informational?style=flat-square&logo=python)
![GitHub](https://img.shields.io/badge/API-Telegram_Bot-informational?style=flat-square&logo=telegram)
[![GitHub](https://img.shields.io/badge/license-GPL+MIT-informational?style=flat-square)](README.md#license)
[![GitHub forks](https://img.shields.io/github/forks/awalon/MailToTelegramForwarder?style=flat-square)](https://github.com/awalon/MailToTelegramForwarder/network) 
[![GitHub stars](https://img.shields.io/github/stars/awalon/MailToTelegramForwarder?style=flat-square)](https://github.com/awalon/MailToTelegramForwarder/stargazers)

## Description

MailToTelegramForwarder is a Python based daemon that will fetch mails 
from a remote IMAP server and forward them via Telegram API. 
There's no need for a dedicated mail server and piping Alias to a 
script; you can use any IMAP capable provider like gmail, outlook, 
self-hosted, etc. to use this feature. Using a dedicated IMAP mailbox 
is strongly recommended.

The bot only sends messages, it does not respond or listen.

## Installation

Installation is very easy for Linux with Systemd and only needs to copy 
and edit some files.

### Prerequisites

To run "mailToTelegramForwarder.py" you have to make sure Python
(Version 3) and following Python libraries are installed: 

`$> pip install $module_name` or `$> apt install python3-$module_name`

```
- configparser
- argparse
- email
- telegram-bot
- imaplib2
```

For Debian 11.x (Bullseye) these packages have to be installed:

**Hint**: python3-python-telegram-bot could be available with Bullseye 
(Testing, 25th of May 2012)
```
sudo apt install python3-python-telegram-bot python3-imaplib2
```

#### Create dedicated system user

Dedicated user is recommended for security reasons, to restrict access 
to the minimum.

```
useradd mail2telegram
```

#### Download and place files
```
wget https://github.com/awalon/MailToTelegramForwarder/archive/master.zip
unzip master.zip

cd MailToTelegramForwarder-master

# "chown" can be skipped, if no dedicated user was created
sudo chown mail2telegram:mail2telegram mailToTelegramForwarder.py
sudo chown mail2telegram:mail2telegram conf/mailToTelegramForwarder.conf

# make script executable
sudo chmod +x mailToTelegramForwarder.py

# create application folder and link executable to default path
sudo mkdir /opt/mailToTelegramForwarder
sudo cp mailToTelegramForwarder.py *.md /opt/mailToTelegramForwarder/
sudo ln -sT /opt/mailToTelegramForwarder/mailToTelegramForwarder.py /usr/local/bin/mailToTelegramForwarder

# create folder for configuration files
sudo mkdir /etc/mail-to-telegram-forwarder
sudo cp conf/mailToTelegramForwarder.conf /etc/mail-to-telegram-forwarder/
```

You should edit `/etc/mail-to-telegram-forwarder/mailToTelegramForwarder.conf`
now.
```
sudo vi /etc/mail-to-telegram-forwarder/mailToTelegramForwarder.conf
```

### Configuration
#### Mail
At least `server`, `user` and `password` have to be updated for access to your
Mail server with IMAP support.

`user`9: On many servers email/username should be in format `user@hostname.com`.

`password`:
If you had enabled 2-factor authentication on your mail server (or Google Account),
you have to create an application password for the bot. 
**Hint**: This script does not support 2-factor authentication.
```
[Mail]
# IMAP server
server: <IMAP mail server>
# IMAP port (default: 993)
#port: <IMAP mail server port like 993>

# IMAP user
user: <mailbox user, ex. my-mail-id>
# IMAP password
password: <mailbox password>

# IMAP connection timout in seconds (default: 60)
#timeout: 60

# use timer in seconds
#refresh: 10

# disconnect after each loop, not recommended for short refresh rates: [True|False]
#disconnect: False
```

`folder` [**Default** 'Inbox']: Can be used to restrict forwarded mail to a
predefined folder. Ex.: Mail folder, which contains preprocessed mails by 
server side ruleset(s).  
```
# IMAP folder on server to check, ex.: INBOX (default)
#folder: <IMAP (sub)folder on server>
```

`search` [**Default** '(UID ${lastUID}:* UNSEEN)']: IMAP search command to filter 
mails handled by this script. Predefined default will forward all `UNSEEN` mails 
since script was started. All these mails will be automatically marked as seen.

Check IMAP specs for further information. Most important **search commands**:

`ALL`: All mails

`UID`: Mails UID on server, which can 
defined a range of mails UIDs on mail server. Ex.: `UID <start>:<end>` or `UID <start>:*`. 

`UNSEEN`: Unseen mails, which will be automatically
marked as seen during search.

`HEADER <header field> "<search string>"`:  Search mails by header fields like
**Subject** or **From**. Ex.: `HEADER From "@google.com"` or 
`HEADER Subject "Some News"`

Supported Placeholder for UID value:
`${lastUID}`: Contains UID of most recent mail on startup and will be updated 
to UID of last forwarded mail. Is used to process new mails only (since start
or last loop).

```
# Check IMAP specs for more info.
#search: (UID ${lastUID}:* UNSEEN HEADER Subject "<Subject or Part of Subject>")
```

`max_length` [**Default** 2000]: Email content will be trimmed, if longer than this
value. HTML messages will be trimmed to this number of characters after unsupported
HTML Elements was removed.

**HINT**: Content will be trimmed after formatting was applied. Hidden HTML or
Markdown elements next to masked characters of Telegram message will be counted too.
Expectation: Forwarded content will be smaller than this value.
```
# max length (characters) of forwarded mail content
#max_length: 2000
```
#### Telegram
`bot_token`: When the bot is registered via [@botfather](https://telegram.me/botfather)
it will get a unique and long token. Enter this token here (ex.: `123456789:djc28e398e223lkje`).

`forward_to_chat_id`: This script posts messages only to predefined chats, which can 
be a group or individual chat. The easiest way to get the ID of a chat is to add the
[@myidbot](https://telegram.me/myidbot) bot to the chat. After ID bot was started with 
`/start` own ID can be requested by `/getid` (ID >  0), if ID bot was added to a group 
chat `/getgroupid` (ID < 0) provides ID of group chat.

Hint: Bot should be added to the chat to be able to post.
```
[Telegram]
# from @BotFather: Like "<Bot ID:Key>"
bot_token: <Bot Token>
# ID of TG chat or user (<ID>, ex.: 123456) who gets forwarded messages.
forward_to_chat_id: <Chat/User ID>
```

**Optional** part of Telegram related configuration:

`markdown_version`[**Default** 2]: Can be used to switch between version 1 and 2 of
Telegrams markdown, if `prefer_html` was set to `False` or mail has no HTML content.
```
# markdown version: [1|2]
#markdown_version: 2
```

If `prefer_html` [**Default** True] was set to `True`, script prefers HTML content
over plain text part and HTML formatted message will be sent to Telgram:

**Hint**: Can be used to get clickable links from HTML mails in forwarded Telegram
message.
```
# prefer HTML messages: [True|False]
#prefer_html: True
```

If both (`forward_mail_content` and `forward_attachment`) was set to `False` only
a short summary having `From`, `Subject` and names of `attached` file(s) will be
forwarded:

```
# forward attachments: [True|False]
#forward_mail_content: True
# forward attachments: [True|False]
#forward_attachment: True
```

See [configuration template](conf/mailToTelegramForwarder.conf) 
`conf/mailToTelegramForwarder.conf` for further information.

### Installing as systemd service
```
sudo cp mail-to-telegram-forwarder@.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### Start systemd daemon

Daemon can be started by configuration file, as multiple configurations
are supported on a single server.

You may enable and start the daemon, now:
```
# start service with default configuration
sudo systemctl start mail-to-telegram-forwarder@mailToTelegramForwarder

# check status
sudo systemctl status mail-to-telegram-forwarder@mailToTelegramForwarder

# enable service, to start default configuration on startup
sudo systemctl enable mail-to-telegram-forwarder@mailToTelegramForwarder
```

## Update
```
# remove old package
rm master.zip

# get most recent code from GitHub
wget https://github.com/awalon/MailToTelegramForwarder/archive/master.zip

# use 'A' to replace [A]ll
unzip master.zip
cd MailToTelegramForwarder-master

# "chown" can be skipped, if no dedicated user was created
sudo chown mail2telegram:mail2telegram mailToTelegramForwarder.py
sudo chown mail2telegram:mail2telegram conf/mailToTelegramForwarder.conf

# make script executable
sudo chmod +x mailToTelegramForwarder.py

# copy script to installation folder
sudo cp mailToTelegramForwarder.py *.md /opt/mailToTelegramForwarder/

# compare configruation file and manually update if needed
diff -y conf/mailToTelegramForwarder.conf /etc/mail-to-telegram-forwarder/mailToTelegramForwarder.conf

# restart service
sudo systemctl restart mail-to-telegram-forwarder@mailToTelegramForwarder

# check status
sudo systemctl status mail-to-telegram-forwarder@mailToTelegramForwarder
```

## Authors

- **Florian Paul Hoberg** - *Initial work* -
  [@florianpaulhoberg](https://github.com/florianpaulhoberg)
- **angelos-se** - *Fork* - 
  [@angelos-se](https://github.com/angelos-se/IMAPBot) based 
  on - *Initial work* - **Luca Weiss** [@z3ntu](https://github.com/z3ntu/IMAPBot)
  [*Abandoned*]
- **Awalon** - *Merged and enhanced Version* - 
  [@awalon](https://github.com/awalon/MailToTelegramForwarder)

## License

This project is licensed under the *GPLv3 License* - see the 
[LICENSE.md](LICENSE.md) file for details -, same parts 
(from IMAPBot) are licensed under the *The MIT License (MIT)* - 
see the [LICENSE-MIT.md](LICENSE-MIT.md) file for details -.
