import requests
import pytest


def is_responsive(url):
    try:
        requests.get(url)
        return True
    except Exception:
        return False


class ServerMixin(object):
    storage_class = None
    wsgi_teardown = None

    @pytest.fixture(scope='session')
    def nextcloud_server(self, docker_ip, docker_services):
        url = 'http://{}:{}'.format(docker_ip,
                                    docker_services.port_for('nextcloud', 80))
        docker_services.wait_until_responsive(
            timeout=30.0, pause=0.1,
            check=lambda: is_responsive(url)
        )
        return url

    @pytest.fixture
    def get_storage_args(self, nextcloud_server, item_type,
                         slow_create_collection):
        def inner(collection='test'):
            args = {
                'username': 'asdf',
                'password': 'asdf',
                'url': nextcloud_server + '/remote.php/dav/'
            }

            if collection is not None:
                args = slow_create_collection(self.storage_class, args,
                                              collection)
            return args
        return inner
