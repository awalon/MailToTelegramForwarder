# IMAP2Telegram

IMAP2Telegram is a Python based daemon that
will fetch mails from a remote IMAP server
and forward the subjects via Telegram API.

### Prerequisites

To run "imap2telegram.py" you have to make sure the follwing Python libraries are installed: 
($> pip install $module_name)
```
- configparser
- argparse
- telegram-send
- imapclient
- email
```

Make sure that 'telegram-send' is configured with a valid token.

### Installing

Installation is very easy for Linux with Systemd and only needs to copy some files.

```
Installing as systemd service:
wget https://github.com/florianpaulhoberg/IMAP2Telegram/archive/master.zip
unzip master.zip
useradd imap2telegram
mkdir /etc/imap2telegram
cd IMAP2Telegram-master
chown telegram:telegram imap2telegram.py
chmod +x imap2telegram.py
chown telegram:telegram imap2telegram.conf
cp imap2telegram.py /usr/local/bin/
cp imap2telegram.conf /etc/imap2telegram/
cp imap2telegram.service /etc/systemd/system/
systemctl daemon-reload

You should edit /etc/imap2telegram/ima2telegram.conf now. 
Again, using a dedicated IMAP mailbox is strongly recommended, because
every new mail will get a delete flag.

You may enable and start the daemon, now:
systemctl enable imap2telegram
systemctl start imap2telegram
```

## Authors

* **Florian Paul Hoberg** - *Initial work* - [@florianpaulhoberg](https://github.com/florianpaulhoberg)

## License

This project is licensed under the GPLv3 License - see the [LICENSE.md](LICENSE.md) file for details
