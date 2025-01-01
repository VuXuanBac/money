from bs4 import BeautifulSoup
from Crypto.Cipher import ChaCha20_Poly1305
from base64 import urlsafe_b64decode
import argon2
import json
import re
import requests
from .parser import NotesParser


AEAD_XCHACHA20POLY1305_IETF_KEYLEN = 32
ENCRYPTED_CONTENT_REGEX = r'(?<="encryptedContent":){[\s\S]*?}(?=,"datePublished")'


class Decryptor:
    def b64_decode(base64_string):
        # Add padding if necessary (Base64 URL-safe can omit padding)
        padding = "=" * (4 - len(base64_string) % 4)
        base64_string += padding
        return urlsafe_b64decode(base64_string)

    def get_password_from_url(url: str):
        splits = url.split("#key=") + [""]
        key = splits[1]
        return Decryptor.b64_decode(key) if key else None

    # https://github.com/streetwriters/notesnook/blob/master/apps/monograph/app/components/monographpost/index.tsx#L689
    def decrypt(
        password: bytes,
        cipher: str,
        iv: str = None,
        salt: str = None,
        length: str = None,
    ):
        # Decode the base64 strings to get the actual binary data
        if isinstance(password, str):
            password = password.encode()
        iv = Decryptor.b64_decode(iv)
        ciphertext = Decryptor.b64_decode(cipher)
        salt = Decryptor.b64_decode(salt)

        key = argon2.low_level.hash_secret_raw(
            secret=password,
            salt=salt,
            time_cost=3,
            memory_cost=8 * 1024,
            parallelism=1,
            hash_len=AEAD_XCHACHA20POLY1305_IETF_KEYLEN,
            type=argon2.Type.I,
        )

        # XChaCha20_Poly1305 is 24-bytes Nonce version
        cipher = ChaCha20_Poly1305.new(key=key, nonce=iv)

        decrypted = cipher.decrypt(ciphertext)
        decrypted_obj = (
            json.loads(decrypted[:length] if length else decrypted) if decrypted else {}
        )

        # Output the plaintext as a string
        return decrypted_obj.get("data", "")


class NotesnookParser(NotesParser):
    def get_encrypted_data(response_text: str) -> dict:
        match = re.search(ENCRYPTED_CONTENT_REGEX, response_text)
        if not match:
            return {}
        return json.loads(match.group())

    def parse(monograph_url: str) -> list:
        response = requests.get(monograph_url)
        if not response.status_code == 200:
            raise RuntimeError("Fail to get Notesnook note")

        encrypted_data = NotesnookParser.get_encrypted_data(response.text)
        password = Decryptor.get_password_from_url(monograph_url)
        if encrypted_data and not password:
            raise RuntimeError("Require password to parse Notesnook note")
        if not encrypted_data:
            text = response.text
        else:
            try:
                text = Decryptor.decrypt(password=password, **encrypted_data)
            except:
                raise RuntimeError(
                    "Fail to decrypt Notesnook note, maybe because of wrong password"
                )
        if not text:
            raise RuntimeError("Fail to parse Notesnook note")

        soup = BeautifulSoup(text, "html.parser")

        tables = soup.find_all("table")

        data = []
        for table in tables:
            data.extend(NotesParser.parse_table(table))

        return data
