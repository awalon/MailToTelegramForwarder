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

```

Make sure that 'telegram-send' is configured with a valid token.

### Installing

Installation is very easy for Linux with Systemd and only needs to copy some files.

```
fixme
```



## Authors

* **Florian Paul Hoberg** - *Initial work* - [@florianpaulhoberg](https://github.com/florianpaulhoberg)

## License

This project is licensed under the GPLv3 License - see the [LICENSE.md](LICENSE.md) file for details
