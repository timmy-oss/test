
from hashlib import new
from uuid import uuid4
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import Field
from models.user import UserInModel, UserOutModel, UserDBModel
from models.wallet import CoinWalletModel, CoinWalletModelDB
from fastapi.encoders import jsonable_encoder
from config import db
from datetime import datetime, timedelta
from config import settings
from fastapi.security import OAuth2PasswordBearer
from datetime import datetime
from uuid import uuid4
from lib import bitcoin_wallet, secret_phrase, litecoin_wallet, ethereum_wallet, binance_wallet, celo_wallet
from passlib.context import CryptContext
from passlib.context import CryptContext


router = APIRouter(
    prefix='/users',
    tags=['users'],
    responses={
        404: {"description": "User does not exist"}
    }
)

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


# Helpers

def create_username(name: str):
    name = ''.join(name.split(" "))
    time = ''.join(str(datetime.now().timestamp()).split('.'))
    return "{0}_{1}".format(name, time)


def get_hash(text):
    return pwd_context.hash((text))


# Backkground tasks
async def create_wallets(new_user: UserOutModel):

    backup_phrase = secret_phrase.generate_secret_phrase()

    bitcoin_wallet_info = bitcoin_wallet.generate_bitcoin_wallet(
        backup_phrase, new_user.username)

    litecoin_wallet_info = litecoin_wallet.generate_litecoin_wallet(
        backup_phrase, new_user.username)

    ethereum_wallet_info = ethereum_wallet.generate_ethereum_wallet(
        backup_phrase, new_user.username)

    binance_wallet_info = binance_wallet.generate_binance_wallet(
        backup_phrase, new_user.username)

    celo_wallet_info = celo_wallet.generate_celo_wallet(
        backup_phrase, new_user.username)

    bitcoin_account_db = CoinWalletModelDB(
        identifier=str(uuid4()),
        coinName='Bitcoin',
        coinTicker='BTC',
        coinDescription="Bitcoin Protocol",
        created=datetime.now().timestamp(),
        derivationPath=bitcoin_wallet_info['path'],
        lastUpdated=datetime.now().timestamp(),
        networkId=None,
        networkName='Bitcoin',
        address=bitcoin_wallet_info['address'],
        ownerId=new_user.identifier,
        pkHash=get_hash(bitcoin_wallet_info['wif_key']),

    )

    litecoin_account_db = CoinWalletModelDB(
        identifier=str(uuid4()),
        coinName='Litecoin',
        coinTicker='LTC',
        coinDescription="Litecoin Protocol",
        created=datetime.now().timestamp(),
        derivationPath=litecoin_wallet_info['path'],
        lastUpdated=datetime.now().timestamp(),
        networkId=None,
        networkName='Litecoin',
        address=litecoin_wallet_info['address'],
        ownerId=new_user.identifier,
        pkHash=get_hash(litecoin_wallet_info['wif_key']),

    )

    binance_account_db = CoinWalletModelDB(
        identifier=str(uuid4()),
        coinName='Smartchain',
        coinTicker='BNB',
        coinDescription="Binance Smartchain",
        created=datetime.now().timestamp(),
        derivationPath=binance_wallet_info['path'],
        lastUpdated=datetime.now().timestamp(),
        networkId=56,
        networkName='Binance Smartchain Mainnet',
        address=binance_wallet_info['address'],
        ownerId=new_user.identifier,
        pkHash=get_hash(binance_wallet_info['private_key']),

    )

    ethereum_account_db = CoinWalletModelDB(
        identifier=str(uuid4()),
        coinName='Ether',
        coinTicker='ETH',
        coinDescription="Ethereum",
        created=datetime.now().timestamp(),
        derivationPath=ethereum_wallet_info['path'],
        lastUpdated=datetime.now().timestamp(),
        networkId=1,
        networkName='Ethereum Mainnet',
        address=ethereum_wallet_info['address'],
        ownerId=new_user.identifier,
        pkHash=get_hash(ethereum_wallet_info['private_key']),

    )

    celo_account_db = CoinWalletModelDB(
        identifier=str(uuid4()),
        coinName='Celo',
        coinTicker='CELO',
        coinDescription="Celo",
        created=datetime.now().timestamp(),
        derivationPath=celo_wallet_info['path'],
        lastUpdated=datetime.now().timestamp(),
        networkId=42220,
        networkName='Celo Mainnet',
        address=celo_wallet_info['address'],
        ownerId=new_user.identifier,
        pkHash=get_hash(celo_wallet_info['private_key']),

    )

    await db.coin_wallets.insert_many([
        bitcoin_account_db.dict(),
        litecoin_account_db.dict(),
        binance_account_db.dict(),
        ethereum_account_db.dict(),
        celo_account_db.dict()

    ])


@router.post('', response_model=UserOutModel, response_model_exclude={'phrase_hash'})
async def create_user(userData: UserInModel, background_tasks: BackgroundTasks):
    data = userData.dict()

    while True:
        username = create_username(data['display_name'])
        existingUser = await db.users.find_one({username: username})
        if not existingUser:
            new_user = UserDBModel(**data, identifier=str(uuid4()),
                                   username=username, created=datetime.now().timestamp())

            await db.users.insert_one(new_user.dict())

            background_tasks.add_task(create_wallets, new_user=new_user)

            return jsonable_encoder(new_user)


@router.get('/{username}', response_model=UserOutModel)
async def get_user_by_username(username: str = Field(min_length=3, max_length=48)):
    user = await db.users.find_one({'username': username})
    if not user:
        raise HTTPException(status_code=404, detail='User does not exist.')
    else:
        return user
