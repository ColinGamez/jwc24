"""Send confirmed notices through the running shared WC24 mail server."""
from email import policy
from email.parser import BytesParser
from http.client import HTTPConnection
import secrets

from .mail import MailStore, WII_ADDRESS


class SharedMailQueue:
    def __init__(self, root, port=8081):
        self.store = MailStore(root)
        self.port = port

    def store_message(self, unused_sender, payload):
        message = BytesParser(policy=policy.default).parsebytes(payload)
        recipients = WII_ADDRESS.findall(str(message.get('To', '')))
        if len(recipients) != 1:
            raise ValueError('Notice must have one paired Wii recipient')
        record = self.store._read_accounts().get(recipients[0])
        if record is None:
            raise ValueError('Wii recipient is not registered with shared mail')
        boundary = 'jwc24-handoff-' + secrets.token_hex(16)
        auth = f'mlid=w{recipients[0]}\r\npasswd={record["password"]}'.encode('ascii')
        body = b''
        for name, value in (('mlid', auth), ('m0', payload)):
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode() + value + b'\r\n')
        body += f'--{boundary}--\r\n'.encode()
        connection = HTTPConnection('127.0.0.1', self.port, timeout=5)
        try:
            connection.request('POST', '/send.cgi', body,
                               {'Content-Type': 'multipart/form-data; boundary=' + boundary})
            response = connection.getresponse()
            data = response.read(4096)
            fields = dict(line.split('=', 1) for line in data.decode('ascii').splitlines() if '=' in line)
            if response.status != 200 or fields.get('cd') != '100' or fields.get('cd0') != '100':
                raise ValueError('Shared mail did not accept notice')
        except Exception:
            raise ValueError('Shared Wii mail queue unavailable; confirmation retained') from None
        finally:
            connection.close()
        return recipients
