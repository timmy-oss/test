from config import db, settings
from lib.security.hashing import password_management
from jose import jwt, JWTError
from typing import Dict, Union
from datetime import timedelta, datetime
from fastapi.security import OAuth2PasswordBearer
from fastapi import HTTPException, Depends
from models.user import UserDBModel
from lib.security.encryption.fernet.core import encrypt as fernet_encrypt, decrypt as fernet_decrypt


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/v1/auth/login')


async def authenticate_client(username: str, password: bytes):
    user = await db.users.find_one({"identifier": username})

    if not user:
        return None

    if not user['password_sent']:
        decrypted_stored_password = fernet_decrypt(
            [settings.master_encryption_key, ], user['password'].encode())
        if str(password.hex()) == str(decrypted_stored_password.hex()):
            return user
        else:
            return False

    if password_management.verify_hash_with_scrypt(settings.encryption_salt, bytes.fromhex(user['password']), password):
        return user

    else:
        return False


async def get_logged_in_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    decrypted_token = fernet_decrypt(
        [settings.master_encryption_key, ], token=token.encode()).decode()

    try:
        payload = jwt.decode(decrypted_token, settings.secret_key,
                             algorithms=[settings.hash_algorithm])
        user_id: str = payload.get('sub')

        if user_id is None:
            raise credentials_exception

    except JWTError as err:
        print("JWT Error : ", err)

        raise credentials_exception

    user = await db.users.find_one({'identifier':  user_id})

    if user is None:
        raise credentials_exception

    return user


async def get_logged_in_active_user(user: Dict = Depends(get_logged_in_user)):
    if user['disabled']:
        raise HTTPException(status_code=401, detail="Unauthorized user")
    return UserDBModel(**user)


def generate_access_token(data: Dict):
    to_encode = data.copy()
    expire = datetime.now() + \
        timedelta(minutes=settings.access_token_expiration_in_minutes)
    to_encode.update({'exp': int(expire.timestamp())})
    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, settings.hash_algorithm)
    return encoded_jwt


async def get_exchange_keys_raw(logged_in_user:  Union[None, UserDBModel], strict=True, replacement_id=None):
    if not logged_in_user and not replacement_id:
        # print("NO LOOKUP")
        raise HTTPException(status_code=401, detail='Unauthorized user')

    user_id = replacement_id if replacement_id else logged_in_user.identifier

    server_rsa = await db.rsa_keypairs.find_one({"user_identifier": user_id})

    if not server_rsa:
        # print("NO ECDH PAIR")
        raise HTTPException(status_code=404, detail='RSA keypair not found')

    user_rsa_session = await db.key_exchange_sessions.find_one({"client_id": user_id})

    if not user_rsa_session and strict:

        raise HTTPException(
            status_code=404, detail='No RSA key exchange session  found')

    decrypted_peer_public_key = None
    decrypted_private_key = None
    decrypted_public_key = None

    if strict:
        decrypted_peer_public_key = fernet_decrypt(
            [settings.master_encryption_key, ], user_rsa_session['peer_public_key'].encode())

    decrypted_private_key = fernet_decrypt(
        [settings.master_encryption_key, ], server_rsa['encrypted_private'].encode())

    decrypted_public_key = fernet_decrypt(
        [settings.master_encryption_key, ], server_rsa['encrypted_public'].encode())

    return {
        "peer_key": decrypted_peer_public_key,
        "key": decrypted_private_key,
        "public_key": decrypted_public_key
    }


async def get_exchange_keys(logged_in_user: Union[UserDBModel, None] = Depends(get_logged_in_active_user)):
    return await get_exchange_keys_raw(logged_in_user)
