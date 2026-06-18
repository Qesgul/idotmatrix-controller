def test_webserver_package_importable():
    import idotctl.webserver
    assert True

def test_session_importable():
    from idotctl.webserver.session import DeviceSession
    assert DeviceSession is not None

def test_staging_importable():
    from idotctl.webserver.staging import ImageStaging
    assert ImageStaging is not None

def test_app_importable():
    from idotctl.webserver.app import app
    assert app is not None
