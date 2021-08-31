import base64
import hashlib
import json
import os

from Crypto.Cipher import ChaCha20

TORR_HASH_KEY = os.getenv('TORR_HASH_KEY')


class AESCipher(object):

    def __init__(self, key):
        self.key = hashlib.sha256(key.encode()).digest()
        self.nonce = 'QWT8HeQOuSU='

    def encrypt(self, raw):
        cipher = ChaCha20.new(key=self.key, nonce=self.nonce)
        ciphertext = cipher.encrypt(str.encode(raw))
        ct = base64.b64encode(ciphertext).decode('utf-8')
        return ct

    def decrypt(self, enc):
        cipher = ChaCha20.new(key=self.key, nonce=self.nonce)
        ciphertext = base64.b64decode(enc)
        plaintext = cipher.decrypt(ciphertext)
        return json.loads(plaintext)


torr_cypher = AESCipher(TORR_HASH_KEY)


if __name__ == '__main__':
    cipher = AESCipher(TORR_HASH_KEY)
    x = cipher.encrypt(json.dumps({'id': '748320', 'folder': 'seed'}))
    print(x)
    y = cipher.decrypt(x)
    print(y)