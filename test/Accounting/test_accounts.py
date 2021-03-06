
import pytest

from Acquire.Accounting import Accounts

from Acquire.Identity import ACLRules, ACLRule, Authorisation

from Acquire.Crypto import PrivateKey, get_private_key

from Acquire.Service import get_service_account_bucket, push_is_running_service


@pytest.fixture(scope="session")
def bucket(tmpdir_factory):
    try:
        return get_service_account_bucket()
    except:
        d = tmpdir_factory.mktemp("objstore")
        push_is_running_service()
        return get_service_account_bucket(str(d))


def test_accounts(bucket):
    for user_guid in [None, "chris@something", "ƒ˚®ø©∆∂µ@¨^ø¨^ø"]:
        if user_guid is None:
            accounts = Accounts(group=user_guid,
                                aclrules=ACLRules.owner(user_guid=None))
        else:
            accounts = Accounts(user_guid=user_guid)

        account_names = ["new account", "chris's checking account",
                         "å∫ç∂´® account"]

        created_accounts = {}

        testing_key = get_private_key("testing")

        for name in account_names:
            authorisation = Authorisation(resource="create_account %s" % name,
                                          testing_key=testing_key,
                                          testing_user_guid=user_guid)

            account = accounts.create_account(
                        name,
                        description="Account: %s" % name,
                        bucket=bucket, authorisation=authorisation)

            assert(name == account.name())

            created_accounts[name] = account

        names = accounts.list_accounts()

        for name in account_names:
            assert(name in names)

        for name in account_names:
            account = accounts.get_account(name, bucket=bucket)
            assert(name == account.name())

            assert(account == created_accounts[name])
