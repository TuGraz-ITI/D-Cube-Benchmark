from cryptography.hazmat.primitives import serialization as crypto_serialization
from cryptography.hazmat.primitives import hashes as crypto_hashes

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.backends import default_backend as crypto_default_backend

from cryptography.exceptions import InvalidSignature

import os
import sys
import logging
import json
import hashlib
import base64

PATH="/testbed/app/keys"

level=logging.DEBUG
FORMAT = "[%(name)16s - %(funcName)12s() ] %(message)s"
logger=logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout,level=level,format=FORMAT)

tii_test_data=b'{"name": "test", "duration": 600, "sig": "Dyw0h5dEkBCkaseTB1ITvS+jG3XusJu4MFjOS8xb26+e3Qfb24g8ZnHIzC4OVX7GLz6AHk5GHGOdVqyxtw8s8YDGyD+jxu7jLpZPxEpaO1YmFr12rUCWqDv1/9Tjs2QP9mRTkY32TwsDxBA/bhB4ML+ADHlCiJ/BK5g1vTzNI/qtyhEQ0jYwgyKrIfYzRXOi75GwNd/few2csEUKz9WJRwNsu0QBjIOG2C118cUFbMa+l7hF3sGgfYDgP4hftSANq4nVBfvna56xiHj6gnK3WkeWaQEc82+ymb1+KIZEszPrEW/xrjXd8I9XqGwFru952jgfIJus+bG/lziJLb5bcw=="}'
graz_test_data=b'{"name": "test", "duration": 600, "sig": "i9GpmkTxGLPleFQ2fWOeaU64fNb4eMk8CUt/yaWUMj3FIKFrazgWsTkfSL/Jt5bK/raIWTCXgSbgjTuIc2fkdNET2Bd6U3jhzIVYMR+D7wCEzcznYhNM6QDX9Qb+TdOuPBJcYukXlvPCEztJqJUGAY9BvCxtdFFYjifFJuOkZ55Fot46vAV3Xdo63m4IAuob9u4er5o4bnc6KzBhE9GNfscBoyaTqTd5w4nFHuJku8W9KrdV0YOwz+GhoiMktax769L8AB7Qg+ZbWQnsXSRbDkpZmakShtOY6PSyV+yKiGurd1c1y4rKwRqLJ3zRHnwAC9BtsZFL5sL/nq7k779GIw=="}'

def generate():

    key = rsa.generate_private_key(
        backend=crypto_default_backend(),
        public_exponent=65537,
        key_size=2048
    )

    private_key = key.private_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PrivateFormat.PKCS8,
        crypto_serialization.NoEncryption()
    )

    public_key = key.public_key().public_bytes(
        crypto_serialization.Encoding.PEM,
        crypto_serialization.PublicFormat.PKCS1,
        #crypto_serialization.Encoding.OpenSSH,
        #crypto_serialization.PublicFormat.OpenSSH
    )

    if os.path.exists(os.path.join(PATH,"pubkey")):
        logger.warning("Public key exists!")
    else:
        with open(os.path.join(PATH,"pubkey"),"wb") as f:
                f.write(public_key)

    if os.path.exists(os.path.join(PATH,"privkey")):
        logger.warning("Private key exists!")
    else:
        with open(os.path.join(PATH,"privkey"),"wb") as f:
                f.write(private_key)

def load():
    if os.path.exists(os.path.join(PATH,"pubkey")):
        logger.debug("Loading Public key...!")
        with open(os.path.join(PATH,"pubkey"),"rb") as f:
            pub_keydata=f.read()
        public_key=crypto_serialization.load_pem_public_key(pub_keydata,
                                                            backend=crypto_default_backend())
    else:
        logger.error("Public key does not exist!")

    if os.path.exists(os.path.join(PATH,"privkey")):
        logger.debug("Loading Private key...!")
        with open(os.path.join(PATH,"privkey"),"rb") as f:
            priv_keydata=f.read()
        private_key=crypto_serialization.load_pem_private_key(priv_keydata,
                                                              backend=crypto_default_backend(),
                                                              password = None)
    else:
        logger.error("Private key does not exist!")

    return (public_key,private_key)

def apitest():
    job={"name":"test","duration":"600"}
    #job={"name":"e2e_first","description":"myfirsttest","duration":"600"}
    with open(os.path.join(PATH,"privkey"),"rb") as f:
        pub_keydata=f.read()
    public_key=crypto_serialization.load_pem_private_key(pub_keydata,
                                                        backend=crypto_default_backend(),
                                                        password = None
    )

    message=json.dumps(job).encode("ascii")
    prehashed = hashlib.sha256(message).hexdigest().encode("ascii")

    sig = public_key.sign(
        prehashed,
        padding.PSS(
            mgf=padding.MGF1(crypto_hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH),
        crypto_hashes.SHA256())

    job["sig"]=base64.b64encode(sig).decode("ascii")
    signed_message=json.dumps(job).encode("ascii")
    logger.info(signed_message)

def selftest(pubkey,privkey):
    job={}
    job["name"]="test"
    job["duration"]=600
    message=json.dumps(job).encode("ascii")
    prehashed = hashlib.sha256(message).hexdigest().encode("ascii")

    sig = privkey.sign(
        prehashed,
        padding.PSS(
            mgf=padding.MGF1(crypto_hashes.SHA256()),
            salt_length=padding.PSS.MAX_LENGTH),
        crypto_hashes.SHA256())

    job["sig"]=base64.b64encode(sig).decode("ascii")
    signed_message=json.dumps(job).encode("ascii")

    decoded_msg=json.loads(signed_message.decode("ascii"))
    decoded_sig=decoded_msg["sig"].encode("ascii")
    decoded_msg.pop("sig")

    inc_msg=json.dumps(decoded_msg).encode("ascii")
    inc_sig=base64.b64decode(decoded_sig)
    inc_prehashed = hashlib.sha256(inc_msg).hexdigest().encode("ascii")

    try:
        pubkey.verify(
            inc_sig,
            inc_prehashed,
            padding.PSS(
                mgf=padding.MGF1(crypto_hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH),
            crypto_hashes.SHA256())
        logger.info('Signature valid!')
    except InvalidSignature:
        logger.error('Signature invalid!')

    job={}
    job["name"]="test2"
    job["duration"]=600
    attack_message=json.dumps(job).encode("ascii")

    attack_prehashed = hashlib.sha256(attack_message).hexdigest().encode("ascii")

    try:
        pubkey.verify(
            inc_sig,
            attack_prehashed,
            padding.PSS(
                mgf=padding.MGF1(crypto_hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH),
            crypto_hashes.SHA256())
        logger.info('Signature valid (this is bad!)!')
    except InvalidSignature:
        logger.error('Signature invalid (should be)!')

def tii_test():
    logger.info("TII test...!")
    logger.debug("Loading TII Public key...!")
    with open(os.path.join(PATH,"tii"),"rb") as f:
        pub_keydata=f.read()
    public_key=crypto_serialization.load_pem_public_key(pub_keydata,
                                                        backend=crypto_default_backend()
    )

    decoded_msg=json.loads(tii_test_data.decode("ascii"))
    decoded_sig=decoded_msg["sig"].encode("ascii")
    decoded_msg.pop("sig")

    inc_msg=json.dumps(decoded_msg).encode("ascii")
    inc_sig=base64.b64decode(decoded_sig)
    inc_prehashed = hashlib.sha256(inc_msg).hexdigest().encode("ascii")

    try:
        public_key.verify(
            inc_sig,
            inc_prehashed,
            padding.PSS(
                mgf=padding.MGF1(crypto_hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH),
            crypto_hashes.SHA256())
        logger.info('TII Signature valid!')
    except InvalidSignature:
        logger.error('TII Signature invalid!')

def graz_test():
    logger.info("Graz test...!")
    logger.debug("Loading Graz Public key...!")
    with open(os.path.join(PATH,"graz"),"rb") as f:
        pub_keydata=f.read()
    public_key=crypto_serialization.load_pem_public_key(pub_keydata,
                                                        backend=crypto_default_backend()
    )

    decoded_msg=json.loads(graz_test_data.decode("ascii"))
    decoded_sig=decoded_msg["sig"].encode("ascii")
    decoded_msg.pop("sig")

    inc_msg=json.dumps(decoded_msg).encode("ascii")
    inc_sig=base64.b64decode(decoded_sig)
    inc_prehashed = hashlib.sha256(inc_msg).hexdigest().encode("ascii")

    try:
        public_key.verify(
            inc_sig,
            inc_prehashed,
            padding.PSS(
                mgf=padding.MGF1(crypto_hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH),
            crypto_hashes.SHA256())
        logger.info('Graz Signature valid!')
    except InvalidSignature:
        logger.error('Graz Signature invalid!')

def main():
    os.makedirs(PATH, exist_ok=True)
    generate()
    (pubkey,privkey) = load()
    selftest(pubkey,privkey)
    tii_test()
    graz_test()
    apitest()


if __name__ == "__main__":
    main()

