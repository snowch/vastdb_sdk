"""VAST database session.

It should be used to interact with a specific VAST cluster.
For more details see:
- [Virtual IP pool configured with DNS service](https://support.vastdata.com/s/topic/0TOV40000000FThOAM/configuring-network-access-v50)
- [S3 access & secret keys on VAST cluster](https://support.vastdata.com/s/article/UUID-4d2e7e23-b2fb-7900-d98f-96c31a499626)
- [Tabular identity policy with the proper permissions](https://support.vastdata.com/s/article/UUID-14322b60-d6a2-89ac-3df0-3dfbb6974182)
"""

from . import internal_commands
from . import transaction

import boto3

import os


class Session:
    """VAST database session."""

    def __init__(self, access=None, secret=None, endpoint=None):
        """Connect to a VAST Database endpoint, using specified credentials."""
        if access is None:
            access = os.environ['AWS_ACCESS_KEY_ID']
        if secret is None:
            secret = os.environ['AWS_SECRET_ACCESS_KEY']
        if endpoint is None:
            endpoint = os.environ['AWS_S3_ENDPOINT_URL']

        self.api = internal_commands.VastdbApi(endpoint, access, secret)
        self.s3 = boto3.client('s3',
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            endpoint_url=endpoint)

    def __repr__(self):
        return f'{self.__class__.__name__}(endpoint={self.api.url}, access={self.api.access_key})'

    def transaction(self):
        """Create a non-initialized transaction object.

        It should be used as a context manager:

            with session.transaction() as tx:
                tx.bucket("bucket").create_schema("schema")
        """
        return transaction.Transaction(self)
