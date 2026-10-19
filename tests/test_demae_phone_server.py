from http.client import HTTPConnection
from pathlib import Path
import tempfile
import threading
import unittest
from jwc24.demae_handoff import HandoffStore
from jwc24.demae_mail_queue import SharedMailQueue
from jwc24.mail import MailStore
from jwc24.mail_server import create_mail_server
from tools.demae_phone_server import create_server


class PhoneHandoffTests(unittest.TestCase):
    def test_selected_branch_link_is_rendered_without_confirming(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mail = MailStore(root / 'mail')
            mail.register('1234567890123456')
            handoffs = HandoffStore(root / 'handoff.sqlite')
            context = {'restaurant_id': 'hotpepper:J000000001', 'name': '<Branch & Shop>',
                       'provider_url': 'https://demae-can.com/shop/menu/1234567'}
            token = handoffs.create('1234567890123456', restaurant=context)
            phone = create_server('127.0.0.1', 0, handoffs, mail)
            worker = threading.Thread(target=phone.serve_forever, daemon=True)
            worker.start()
            try:
                connection = HTTPConnection(*phone.server_address, timeout=3)
                connection.request('GET', '/h/' + token)
                response = connection.getresponse()
                body = response.read().decode()
                connection.close()
                self.assertEqual(response.status, 200)
                self.assertIn('href="' + context['provider_url'] + '"', body)
                self.assertIn('&lt;Branch &amp; Shop&gt;', body)
                self.assertNotIn('<Branch & Shop>', body)
                self.assertIn('does not transfer a Wii basket', body)
                self.assertFalse(handoffs.status(token)['confirmed'])
                self.assertEqual(len(mail.pending('1234567890123456')), 0)
            finally:
                phone.shutdown()
                phone.server_close()
                worker.join(timeout=3)

    def test_phone_confirmation_delivers_once_via_shared_mail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            mail = MailStore(root / 'mail')
            recipient = '1234567890123456'
            mail.register(recipient)
            mail_server = create_mail_server('127.0.0.1', 0, mail)
            handoffs = HandoffStore(root / 'handoff.sqlite')
            token = handoffs.create(recipient)
            phone = create_server('127.0.0.1', 0, handoffs, SharedMailQueue(root / 'mail', mail_server.server_port))
            workers = [threading.Thread(target=s.serve_forever, daemon=True) for s in (mail_server, phone)]
            for worker in workers:
                worker.start()
            try:
                connection = HTTPConnection(*phone.server_address, timeout=3)
                connection.request('GET', '/h/' + token)
                response = connection.getresponse()
                self.assertIn(b'I placed my order', response.read())
                self.assertEqual(response.getheader('Referrer-Policy'), 'no-referrer')
                self.assertEqual(len(mail.pending(recipient)), 0)
                connection.close()
                for _ in range(2):
                    connection = HTTPConnection(*phone.server_address, timeout=3)
                    connection.request('POST', '/h/' + token, b'')
                    response = connection.getresponse()
                    self.assertEqual(response.status, 303)
                    response.read()
                    connection.close()
                self.assertEqual(len(mail.pending(recipient)), 1)
                connection = HTTPConnection(*phone.server_address, timeout=3)
                connection.request('POST', '/h/' + token, b'', {'Origin': 'https://unrelated.example'})
                response = connection.getresponse()
                self.assertEqual(response.status, 403)
                response.read()
                connection.close()
            finally:
                for server in (phone, mail_server):
                    server.shutdown()
                    server.server_close()
                for worker in workers:
                    worker.join(timeout=3)
