import sys


def test_backend_test_stubs_do_not_install_zep_cloud():
    import conftest as test_conftest

    sys.modules.pop("zep_cloud", None)
    sys.modules.pop("zep_cloud.client", None)

    test_conftest._install_test_stubs()

    assert "zep_cloud" not in sys.modules
    assert "zep_cloud.client" not in sys.modules
