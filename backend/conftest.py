def pytest_configure(config):
    config.addinivalue_line("markers", "real_youtube: read-only tests that call real YouTube APIs")
